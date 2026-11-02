"""Платежи — прямая оплата через ЮKassa API."""
import logging

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.config import Config
from bot_v2.db.repositories import PaymentRepo, ParticipantRepo, UserRepo
from bot_v2.keyboards import kb_tariffs, kb_tariff_detail, kb_curator_notify
from bot_v2.services.i18n import t
from bot_v2.services.mizan_os import notify_mizan_payment
from bot_v2.services.program import get_tariff, get_tariff_view
from bot_v2.services.yookassa_svc import create_payment

logger = logging.getLogger(__name__)

TARIFF_LEVEL_MAP = {
    "vakt":     "А",
    "s1_month": "Б",
    "s1_full":  "Б",
    "s3_full":  "Б",
}

router = Router(name="payments")


async def _effective_price(session: AsyncSession, tariff_id: str, user_id: int) -> tuple[int, int | None]:
    """Цена с учётом персональных предложений.

    Возвращает (цена, unix-время окончания скидки или None).
    Единый источник правды для карточки тарифа и создания платежа —
    чтобы человек видел ту же цену, которую потом платит.
    """
    import time as _time
    from bot_v2.db.repositories import SettingsRepo

    tariff = get_tariff(tariff_id)
    price = tariff["price"] if tariff else 0
    now = int(_time.time())
    repo = SettingsRepo(session)

    # Скидка 999 ₽ на Старт после Кораблика (3 часа)
    if tariff_id == "vakt":
        val = await repo.get(f"korablik_offer:{user_id}")
        try:
            if val and int(val) > now:
                return 999, int(val)
        except ValueError:
            pass

    # Скидка 3 500 ₽ на Путь после Старта (48 часов)
    if tariff_id == "s1_month":
        val = await repo.get(f"s1_offer_at:{user_id}")
        try:
            if val and int(val) > now:
                return 3_500, int(val)
        except ValueError:
            pass
        return 5_000, None

    return price, None


def _left_str(expires_at: int) -> str:
    import time as _time
    left = max(0, expires_at - int(_time.time()))
    h, m = divmod(left // 60, 60)
    return f"{h} ч {m} мин" if h else f"{m} мин"


def _price_str(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _vakt_card_text(price: int, expires_at: int | None) -> str:
    """Продающая карточка IQ Barakah Старт (ru)."""
    base = get_tariff("vakt")["price"]
    if expires_at and price < base:
        price_line = (
            f"💰 {_price_str(base)} ₽ → *{_price_str(price)} ₽*\n"
            f"🎁 Цена за пройденную диагностику — действует ещё {_left_str(expires_at)}"
        )
    else:
        price_line = f"💰 *{_price_str(price)} ₽* — разовая оплата, без подписки"
    return (
        "🌱 *IQ Barakah Старт*\n"
        "_6 шагов — по одному в неделю — чтобы вернуть ритм дня_\n\n"
        "*Что меняется уже в первые 2 недели:*\n"
        "• Утро начинается с Фаджра, а не с телефона\n"
        "• День выстроен вокруг намазов\n"
        "• Вечерний разбор — 5 минут, без самобичевания\n"
        "• Рядом брат/сестра по пути и общая группа\n\n"
        "⏱ 15 минут утром + 5 минут вечером\n"
        "🤝 Не почувствуешь сдвиг в первую неделю — напиши куратору, разберёмся\n\n"
        f"{price_line}"
    )


def _kb_vakt_offer(price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Начать за {_price_str(price)} ₽", callback_data="pay:vakt")],
        [InlineKeyboardButton(text="📋 Все программы", callback_data="show_tariffs")],
    ])


async def _tariff_card(session: AsyncSession, tariff_id: str, user_id: int, lang: str):
    """Текст и клавиатура карточки тарифа с актуальной ценой."""
    tariff = get_tariff(tariff_id)
    tariff_view = get_tariff_view(tariff_id, lang) or tariff
    price, expires_at = await _effective_price(session, tariff_id, user_id)
    if tariff_id == "vakt" and lang == "ru":
        return _vakt_card_text(price, expires_at), _kb_vakt_offer(price)
    text = f"*{tariff_view['name']}*\n_{tariff_view['desc']}_\n\n💰 {_price_str(price)} ₽"
    if expires_at and price < tariff["price"]:
        text = (
            f"*{tariff_view['name']}*\n_{tariff_view['desc']}_\n\n"
            f"💰 {_price_str(tariff['price'])} ₽ → *{_price_str(price)} ₽*\n"
            f"🎁 Специальная цена — действует ещё {_left_str(expires_at)}"
        )
    return text, kb_tariff_detail(tariff_id, lang)


@router.callback_query(F.data.startswith("offer:"))
async def cb_offer(call: CallbackQuery, session: AsyncSession):
    """Карточка конкретного тарифа новым сообщением — прямой путь из рекомендации
    к оплате, без промежуточного меню всех тарифов."""
    await send_offer(call, session, call.data.split(":")[1])


async def send_offer(call: CallbackQuery, session: AsyncSession, tariff_id: str):
    await call.answer()
    lang = await _user_lang(session, call.from_user.id)
    if not get_tariff(tariff_id):
        await call.message.answer(t(lang, "tariffs.not_found"))
        return
    text, kb = await _tariff_card(session, tariff_id, call.from_user.id, lang)
    await call.message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data == "show_tariffs")
async def cb_show_tariffs(call: CallbackQuery, session: AsyncSession):
    await call.answer()
    lang = await _user_lang(session, call.from_user.id)
    await call.message.edit_text(
        t(lang, "tariffs.title"), parse_mode="Markdown", reply_markup=kb_tariffs(lang)
    )


@router.callback_query(F.data.startswith("tariff:"))
async def cb_tariff_detail(call: CallbackQuery, session: AsyncSession):
    lang = await _user_lang(session, call.from_user.id)
    tariff_id = call.data.split(":")[1]
    tariff = get_tariff(tariff_id)
    if not tariff:
        await call.answer(t(lang, "tariffs.not_found"))
        return
    await call.answer()
    text, kb = await _tariff_card(session, tariff_id, call.from_user.id, lang)
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery, session: AsyncSession, config: Config):
    await call.answer()
    lang = await _user_lang(session, call.from_user.id)
    tariff_id = call.data.split(":")[1]
    logger.info("cb_pay: user=%s tariff=%s", call.from_user.id, tariff_id)

    tariff = get_tariff(tariff_id)
    if not tariff:
        logger.warning("cb_pay: tariff not found: %s", tariff_id)
        await call.message.answer(t(lang, "tariffs.not_found"))
        return

    # Защита от дублей — проверяем есть ли уже paid платёж по этому тарифу
    from sqlalchemy import select as _sa_select
    from bot_v2.db.models import Payment as _Payment
    existing = await session.scalar(
        _sa_select(_Payment).where(
            _Payment.user_id == call.from_user.id,
            _Payment.tariff_id == tariff_id,
            _Payment.status == "paid",
        )
    )
    if existing:
        # call.answer() уже вызван в начале хендлера — повторный answer Telegram
        # отклоняет, и человек видел «мёртвую» кнопку. Отвечаем сообщением.
        logger.info("cb_pay: duplicate paid tariff %s for user %s", tariff_id, call.from_user.id)
        tariff_view = get_tariff_view(tariff_id, lang) or tariff
        await call.message.answer(
            f"✅ У тебя уже есть доступ к *{tariff_view['name']}*.\n\n"
            f"Уроки — в разделе «📖 Мой путь» в меню внизу. 🌿",
            parse_mode="Markdown",
        )
        return

    if tariff_id in ("jamaat", "leader"):
        tariff_view = get_tariff_view(tariff_id, lang) or tariff
        user = await UserRepo(session).get(call.from_user.id)
        name = user.name if user else str(call.from_user.id)
        username = user.username if user and user.username else None
        from bot_v2.keyboards.inline import kb_curator_contact
        # Уведомляем куратора
        for curator_id in config.curator_ids:
            try:
                await call.bot.send_message(
                    chat_id=curator_id,
                    text=(
                        f"📩 *Запрос на {tariff_view['name']}*\n\n"
                        f"👤 {name} (`{call.from_user.id}`)\n"
                        f"📦 {tariff_view['name']}\n\n"
                        f"Свяжись с участником для обсуждения условий."
                    ),
                    parse_mode="Markdown",
                    reply_markup=kb_curator_contact(call.from_user.id, username),
                )
            except Exception:
                pass
        await call.message.answer(
            f"✅ Твой запрос на *{tariff_view['name']}* отправлен!\n\n"
            f"Куратор свяжется с тобой в ближайшее время. 🌿",
            parse_mode="Markdown",
        )
        return

    logger.info("cb_pay: shop_id=%s secret_set=%s", config.yookassa_shop_id, bool(config.yookassa_secret_key))
    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        logger.error("cb_pay: YooKassa credentials missing!")
        await call.message.answer("⚠️ Оплата временно недоступна. Напишите куратору: @iqbarakah")
        return

    user_id = call.from_user.id
    user = await UserRepo(session).get(user_id)
    tariff_view = get_tariff_view(tariff_id, lang) or tariff

    # Персональные скидки: 999 ₽ на Старт после Кораблика, 3 500 ₽ на Путь после Старта
    price, offer_expires = await _effective_price(session, tariff_id, user_id)
    discount_active = bool(offer_expires) and price < tariff["price"]

    logger.info("cb_pay: creating payment tariff=%s price=%s user=%s", tariff_id, price, user_id)
    payment = await create_payment(
        shop_id=config.yookassa_shop_id,
        secret_key=config.yookassa_secret_key,
        amount=price,
        description=f"{tariff_view['name']} — IQ Barakah",
        return_url="https://t.me/iqbaraka_bot",
        metadata={"tariff_id": tariff_id, "user_id": str(user_id)},
    )
    logger.info("cb_pay: payment result=%s", payment)

    if not payment or payment.get("error"):
        err_detail = payment.get("detail", {}) if payment else {}
        err_code = err_detail.get("code", "unknown")
        err_desc = err_detail.get("description", "нет описания")
        err_http = payment.get("status_code", "?") if payment else "?"
        await call.message.answer(
            f"⚠️ Ошибка ЮKassa [{err_http}]: `{err_code}`\n_{err_desc}_",
            parse_mode="Markdown"
        )
        return

    # Записываем pending-платёж
    await PaymentRepo(session).create(
        user_id=user_id,
        tariff_id=tariff_id,
        amount=price,
        yoo_payment_id=payment["id"],
    )

    name = user.name if user else "участник"
    price_str = _price_str(price)
    # Сообщение уходит без parse_mode — поэтому без markdown-зачёркиваний,
    # раньше человек видел буквально «~~1 500 ₽~~».
    discount_line = (
        f"🎁 Специальная цена — действует ещё {_left_str(offer_expires)}\n\n" if discount_active else ""
    )
    old_price_line = f"{_price_str(tariff['price'])} ₽ → " if discount_active else ""
    text = (
        f"💳 {tariff_view['name']}\n\n"
        f"{discount_line}"
        f"💰 Сумма: {old_price_line}{price_str} ₽\n\n"
        f"Нажми кнопку ниже — оплати на сайте ЮKassa.\n"
        f"После оплаты нажми «✅ Я оплатил» — урок придёт сразу 🌱"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment["confirmation_url"])],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_pay:{tariff_id}:{payment['id']}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="show_tariffs")],
    ])
    logger.info("Sending payment message to user %s, payment_id=%s", call.from_user.id, payment["id"])
    try:
        await call.message.answer(text, reply_markup=kb)
    except Exception as e:
        logger.error("Failed to send payment message: %s", e)
        await call.message.answer(f"✅ Платёж создан! Перейди по ссылке: {payment['confirmation_url']}")

    # Уведомляем куратора о заказе
    for curator_id in config.curator_ids:
        try:
            await call.bot.send_message(
                chat_id=curator_id,
                text=(
                    f"🔔 *Новый заказ*\n\n"
                    f"👤 {name} (`{user_id}`)\n"
                    f"📦 {tariff['name']} · {price:,} ₽\n"
                    f"🆔 `{payment['id']}`"
                ).replace(",", " "),
                parse_mode="Markdown",
                reply_markup=kb_curator_notify(user_id, tariff_id, user.username if user and user.username else None),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("check_pay:"))
async def cb_check_payment(call: CallbackQuery, session: AsyncSession, config: Config):
    """Пользователь нажал «✅ Я оплатил» — проверяем статус в ЮKassa прямо сейчас."""
    await call.answer("Проверяю платёж...", show_alert=False)
    lang = await _user_lang(session, call.from_user.id)

    parts = call.data.split(":")
    if len(parts) < 3:
        await call.message.answer("❌ Ошибка. Попробуйте снова.")
        return

    tariff_id = parts[1]
    payment_id = parts[2]

    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        await call.answer("⚠️ Проверка временно недоступна. Подождите 2 минуты.", show_alert=True)
        return

    from bot_v2.services.yookassa_svc import get_payment_status
    from bot_v2.db.repositories import PaymentRepo, ParticipantRepo
    from bot_v2.services.program import get_tariff_view
    from bot_v2.handlers.program import send_weekly_lesson
    import datetime as _dt
    from datetime import timezone

    status = await get_payment_status(config.yookassa_shop_id, config.yookassa_secret_key, payment_id)

    if status == "succeeded":
        tariff = get_tariff(tariff_id)
        tariff_view = get_tariff_view(tariff_id, lang) or tariff
        tariff_name = tariff_view["name"] if tariff_view else tariff_id
        level = TARIFF_LEVEL_MAP.get(tariff_id)

        # SELECT FOR UPDATE — блокируем строку чтобы concurrent клики не дали двойную активацию
        pay_repo = PaymentRepo(session)
        db_pay = await pay_repo.get_by_yoo_id_for_update(payment_id)

        if db_pay and db_pay.status == "paid":
            user = await UserRepo(session).get(call.from_user.id)
            name = user.name if user else str(call.from_user.id)
            username = user.username if user and user.username else call.from_user.username or ""
            await notify_mizan_payment(
                config,
                payment_id=payment_id,
                telegram_user_id=call.from_user.id,
                amount=db_pay.amount,
                tariff_id=tariff_id,
                product_name=tariff_name,
                customer_name=name,
                telegram_username=username,
                participant_activated=bool(level),
                paid_at=db_pay.paid_at,
            )
            await call.answer("✅ Оплата уже подтверждена! Проверьте сообщения выше.", show_alert=True)
            return

        # Помечаем оплаченным
        if db_pay:
            db_pay.status = "paid"
            db_pay.paid_at = _dt.datetime.now(timezone.utc)
            await session.flush()

            # Начисляем Баракаты рефереру
            from bot_v2.services.barakah import accrue_referral_barakah
            referrer_id = await accrue_referral_barakah(session, db_pay)
            if referrer_id:
                barakah_amount = round(db_pay.amount * 10 / 100)
                try:
                    await call.bot.send_message(
                        referrer_id,
                        f"🎁 *+{barakah_amount} Баракатов!*\n\n"
                        f"Твой друг оплатил программу.\n"
                        f"10% от его оплаты ({db_pay.amount}₽) зачислены тебе.\n\n"
                        f"Посмотреть баланс: /balance",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

        if level:
            p_repo = ParticipantRepo(session)
            participant = await p_repo.activate(call.from_user.id, level=level, week=1)
            await session.flush()

        if tariff_id == "forum_27_06":
            await call.message.edit_text(
                f"✅ *Оплата подтверждена!*\n\n"
                f"📦 {tariff_name}\n\n"
                f"🌿 Отправляю билет...",
                parse_mode="Markdown",
            )
            from bot_v2.services.forum_materials import send_forum_materials
            await send_forum_materials(call.bot, call.from_user.id, session)
        else:
            await call.message.edit_text(
                f"✅ *Оплата подтверждена!*\n\n"
                f"📦 {tariff_name}\n\n"
                f"🌿 _Баракат в каждом шаге_\n\n"
                f"Сейчас пришлю первый урок...",
                parse_mode="Markdown",
            )
            if level:
                try:
                    await send_weekly_lesson(call.bot, call.from_user.id, participant, session, config)
                except Exception as e:
                    logger.warning("send_weekly_lesson after check_pay: %s", e)

        # Уведомляем кураторов
        user = await UserRepo(session).get(call.from_user.id)
        name = user.name if user else str(call.from_user.id)
        username = user.username if user and user.username else call.from_user.username or ""
        await notify_mizan_payment(
            config,
            payment_id=payment_id,
            telegram_user_id=call.from_user.id,
            amount=db_pay.amount if db_pay else (tariff["price"] if tariff else 0),
            tariff_id=tariff_id,
            product_name=tariff_name,
            customer_name=name,
            telegram_username=username,
            participant_activated=bool(level),
            paid_at=db_pay.paid_at if db_pay else None,
        )
        for curator_id in config.curator_ids:
            try:
                await call.bot.send_message(
                    chat_id=curator_id,
                    text=(
                        f"✅ *Оплата подтверждена*\n\n"
                        f"👤 {name} (`{call.from_user.id}`)\n"
                        f"📦 {tariff_name}\n"
                        f"🆔 `{payment_id}`"
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    elif status == "canceled":
        await call.message.edit_text(
            "❌ Платёж отменён.\n\nПопробуйте оплатить снова.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(text="💳 Попробовать снова", callback_data=f"pay:{tariff_id}"),
            ]]),
        )
    else:
        # pending — ещё не оплачен
        await call.answer(
            "⏳ Платёж ещё не завершён.\n\nОплатите на сайте ЮKassa и нажмите снова.",
            show_alert=True,
        )


@router.callback_query(F.data == "contact_curator")
async def cb_contact_curator(call: CallbackQuery, session: AsyncSession, config: Config):
    """Пользователь хочет поговорить с куратором — из апсейла или других мест."""
    await call.answer()
    user = await UserRepo(session).get(call.from_user.id)
    name = user.name if user else call.from_user.full_name

    curator_id = config.curator_ids[0] if config.curator_ids else None
    write_btn = (
        [[InlineKeyboardButton(text="✍️ Написать куратору", url=f"tg://user?id={curator_id}")]]
        if curator_id else []
    )
    await call.message.answer(
        "💬 Напиши куратору — ответим в течение часа.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=write_btn + [
            [InlineKeyboardButton(text="🎓 Все тарифы", callback_data="show_tariffs")],
        ])
    )

    # Уведомляем куратора
    user = await UserRepo(session).get(call.from_user.id)
    username = user.username if user and user.username else None
    open_btn = InlineKeyboardButton(
        text="✍️ Написать",
        url=f"tg://user?id={call.from_user.id}" if not username else f"https://t.me/{username}",
    )
    for curator_id in config.curator_ids:
        try:
            await call.bot.send_message(
                chat_id=curator_id,
                text=(
                    f"💬 *Запрос на контакт с куратором*\n\n"
                    f"👤 {name} (`{call.from_user.id}`)\n"
                    f"Нажал «Поговорить с куратором» в боте."
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[open_btn]]),
            )
        except Exception:
            pass


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
