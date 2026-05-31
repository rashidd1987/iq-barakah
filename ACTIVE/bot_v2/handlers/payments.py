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
from bot_v2.services.program import get_tariff, get_tariff_view
from bot_v2.services.yookassa_svc import create_payment

logger = logging.getLogger(__name__)

TARIFF_LEVEL_MAP = {
    "vakt":    "А",
    "s1_full": "Б",
    "s3_full": "Б",
}

router = Router(name="payments")


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
    tariff_view = get_tariff_view(tariff_id, lang) or tariff
    await call.answer()
    text = f"*{tariff_view['name']}*\n_{tariff_view['desc']}_\n\n💰 {tariff['price']:,} ₽".replace(",", " ")
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb_tariff_detail(tariff_id, lang))


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery, session: AsyncSession, config: Config):
    await call.answer()
    lang = await _user_lang(session, call.from_user.id)
    tariff_id = call.data.split(":")[1]
    tariff = get_tariff(tariff_id)
    if not tariff:
        await call.message.answer(t(lang, "tariffs.not_found"))
        return

    if tariff_id in ("jamaat", "leader"):
        tariff_view = get_tariff_view(tariff_id, lang) or tariff
        await call.message.answer(
            f"*{tariff_view['name']}*\n\n{t(lang, 'payments.manager')}",
            parse_mode="Markdown",
        )
        return

    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        await call.message.answer("⚠️ Оплата временно недоступна. Напишите куратору: @iqbarakah")
        return

    user_id = call.from_user.id
    user = await UserRepo(session).get(user_id)
    tariff_view = get_tariff_view(tariff_id, lang) or tariff

    payment = await create_payment(
        shop_id=config.yookassa_shop_id,
        secret_key=config.yookassa_secret_key,
        amount=tariff["price"],
        description=f"{tariff_view['name']} — IQ Barakah",
        return_url="https://t.me/iqbaraka_bot",
        metadata={"tariff_id": tariff_id, "user_id": str(user_id)},
    )

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
        amount=tariff["price"],
        yoo_payment_id=payment["id"],
    )

    name = user.name if user else "участник"
    text = (
        f"💳 *{tariff_view['name']}*\n"
        f"_{tariff_view['desc']}_\n\n"
        f"💰 Сумма: *{tariff['price']:,} ₽*\n\n"
        f"Нажми кнопку ниже — оплати на сайте ЮKassa.\n"
        f"После оплаты вернись в бот — урок придёт автоматически в течение 2 минут 🌱"
    ).replace(",", " ")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment["confirmation_url"])],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_pay:{tariff_id}:{payment['id']}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="show_tariffs")],
    ])
    await call.message.answer(text, parse_mode="Markdown", reply_markup=kb)

    # Уведомляем куратора о заказе
    for curator_id in config.curator_ids:
        try:
            await call.bot.send_message(
                chat_id=curator_id,
                text=(
                    f"🔔 *Новый заказ*\n\n"
                    f"👤 {name} (`{user_id}`)\n"
                    f"📦 {tariff['name']} · {tariff['price']:,} ₽\n"
                    f"🆔 `{payment['id']}`"
                ).replace(",", " "),
                parse_mode="Markdown",
                reply_markup=kb_curator_notify(user_id, tariff_id),
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
        # Проверяем — не активировали ли уже
        pay_repo = PaymentRepo(session)
        db_pay = await pay_repo.get_by_yoo_id(payment_id)

        if db_pay and db_pay.status == "paid":
            await call.answer("✅ Оплата уже подтверждена! Проверьте сообщения выше.", show_alert=True)
            return

        # Помечаем оплаченным
        if db_pay:
            db_pay.status = "paid"
            db_pay.paid_at = _dt.datetime.now(timezone.utc)
            await session.flush()

        tariff = get_tariff(tariff_id)
        tariff_view = get_tariff_view(tariff_id, lang) or tariff
        tariff_name = tariff_view["name"] if tariff_view else tariff_id

        level = TARIFF_LEVEL_MAP.get(tariff_id)
        if level:
            p_repo = ParticipantRepo(session)
            participant = await p_repo.activate(call.from_user.id, level=level, week=1)
            await session.flush()

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


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
