"""Фоновые задачи: silence_check, Фаджр, пятница, зеркало прогресса."""
import logging
import random
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.engine import get_session_factory
from bot_v2.db.models import Participant, User
from bot_v2.services.program import LEVEL_NAMES, LEVEL_WEEKS

logger = logging.getLogger(__name__)

# Для начинающих (уровень I) — без упоминания намаза
FAJR_MSGS_BEGINNER = [
    (
        "🌅 *Доброе утро!*\n\n"
        "Утро — якорь всего дня. Тот, кто начинает день осознанно — "
        "контролирует своё время, а не плывёт по течению.\n\n"
        "_Одна осознанная минута утром — и ты уже на шаг впереди себя вчерашнего. 🌿_"
    ),
    (
        "🌙 *Ещё тихо — это самое ценное время.*\n\n"
        "Пока весь мир спит, у тебя есть возможность начать день с намерением.\n\n"
        "_Вставай. Подними голову. Сделай один осознанный шаг. 🌿_"
    ),
    (
        "⭐ *Рассвет близко...*\n\n"
        "«Маленькое и постоянное — лучше большого и временного».\n"
        "Одно тихое утро с намерением — это и есть система.\n\n"
        "_Ты строишь что-то настоящее. Шаг за шагом. 🌿_"
    ),
]

# Для практикующих (уровень II и выше)
FAJR_MSGS = [
    (
        "🌅 *Ас-саляму алейкум!*\n\n"
        "Фаджр (рассветная молитва) — якорь дня. Тот, кто поднимается на рассвете — "
        "контролирует своё утро, а утро задаёт весь день.\n\n"
        "_Один намаз — и ты уже победил себя. БаракАллах фикум (да благословит тебя Аллах) 🌿_"
    ),
    (
        "🌙 *Ещё темно — но Аллах уже видит тебя.*\n\n"
        "Эти минуты до рассвета — самые ценные в сутках. "
        "Фаджр — это не просто молитва, это состояние.\n\n"
        "_Вставай и начинай свой день с Аллаха. 🌿_"
    ),
    (
        "⭐ *Рассвет близко...*\n\n"
        "Помнишь? «Маленькое и постоянное — лучше большого и временного». "
        "Один тихий намаз на рассвете — это и есть система.\n\n"
        "_Ин ша Аллах (если пожелает Аллах) — да примет Аллах наш Фаджр. 🌿_"
    ),
]

FRIDAY_MSGS = [
    (
        "🕌 *Джума мубарак (благословенной пятницы)!*\n\n"
        "Один вопрос от Джарваса на эту пятницу:\n\n"
        "_Что на этой неделе ты сделал ради Аллаха — не ради результата, а ради Него?_\n\n"
        "Запиши ответ — даже одно слово. Это и есть мухасаба (честный отчёт себе). 🌿"
    ),
    (
        "🌙 *Баракатной пятницы!*\n\n"
        "Пятница — день рефлексии и благодарности. "
        "Что из инструментов программы зацепило тебя на этой неделе?\n\n"
        "_Даже маленькое и постоянное — уже победа. БаракАллах фикум (да благословит тебя Аллах) 🌿_"
    ),
    (
        "⭐ *Пятничное послание от Джарваса:*\n\n"
        "Мы собираемся вместе в IQ Barakah каждую неделю — "
        "как умма (мусульманская община) собирается на Джуму (пятничную молитву).\n\n"
        "_Как ты? Что радовало тебя на этой неделе? Напиши — я слушаю 🌿_"
    ),
]


async def _get_active_participants(session: AsyncSession) -> list[tuple[Participant, User]]:
    result = await session.execute(
        select(Participant, User)
        .join(User, User.id == Participant.user_id)
        .where(Participant.is_active == True)
    )
    return result.all()


async def job_jarwas_fajr(bot: Bot):
    """Ежедневно 05:30 МСК (02:30 UTC) — Фаджр-напоминание активным участникам."""
    now = datetime.now(timezone.utc)
    async with get_session_factory()() as session:
        rows = await _get_active_participants(session)
        count = 0
        for participant, user in rows:
            last = participant.last_active
            if last and (now - last).days > 14:
                continue
            try:
                # Уровень I → без упоминания намаза
                skill = participant.vakt_level or "I"
                msgs = FAJR_MSGS_BEGINNER if skill == "I" else FAJR_MSGS
                await bot.send_message(
                    chat_id=user.id,
                    text=random.choice(msgs),
                    parse_mode="Markdown",
                )
                count += 1
            except Exception as e:
                logger.warning("jarwas_fajr → %s: %s", user.id, e)
    logger.info("Джарвас Фаджр: %d чел.", count)


async def job_jarwas_friday(bot: Bot):
    """Пятница 20:00 МСК (17:00 UTC) — пятничная рефлексия."""
    now = datetime.now(timezone.utc)
    async with get_session_factory()() as session:
        rows = await _get_active_participants(session)
        count = 0
        for participant, user in rows:
            last = participant.last_active
            if last and (now - last).days > 14:
                continue
            try:
                await bot.send_message(
                    chat_id=user.id,
                    text=random.choice(FRIDAY_MSGS),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🌙 Записать мухасабу", callback_data="start_muhasaba"),
                    ]]),
                )
                count += 1
            except Exception as e:
                logger.warning("jarwas_friday → %s: %s", user.id, e)
    logger.info("Джарвас пятница: %d чел.", count)


async def job_silence_check(bot: Bot, curator_ids: list[int]):
    """Ежедневно 10:00 МСК — проверяет молчание участников."""
    now = datetime.now(timezone.utc)
    async with get_session_factory()() as session:
        rows = await _get_active_participants(session)
        for participant, user in rows:
            last = participant.last_active
            if not last:
                continue
            try:
                last = last.replace(tzinfo=timezone.utc) if last.tzinfo is None else last
            except Exception:
                continue
            days = (now - last).days
            first_name = (user.name or "Брат").split()[0]

            if days == 3:
                try:
                    await bot.send_message(
                        chat_id=user.id,
                        parse_mode="Markdown",
                        text=(
                            f"🌿 Ас-саляму алейкум, *{first_name}*!\n\n"
                            "Мы заметили что тебя не было 3 дня.\n\n"
                            "Всё хорошо? Жизнь бывает разной — и это нормально. "
                            "Мы здесь, без осуждения. 🤍\n\n"
                            "Когда будешь готов — просто нажми кнопку или напиши что-нибудь."
                        ),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("💪 Я здесь, продолжаю", callback_data="silence_back"),
                        ]]),
                    )
                except Exception as e:
                    logger.warning("silence_check day3 → %s: %s", user.id, e)

            elif days == 7:
                uname = f"@{user.username}" if user.username else f"ID {user.id}"
                for cid in curator_ids:
                    try:
                        await bot.send_message(
                            chat_id=cid,
                            parse_mode="Markdown",
                            text=(
                                f"⚠️ *Молчание 7 дней*\n\n"
                                f"👤 {user.name} ({uname})\n"
                                f"📊 Уровень {participant.level} · Шаг {participant.week}\n\n"
                                "Напиши ему лично — бот уже отправлял мягкое напоминание на 3-й день."
                            ),
                        )
                    except Exception as e:
                        logger.warning("silence_check day7 curator %s: %s", cid, e)


async def job_progress_mirror(bot: Bot, miniapp_url: str):
    """Воскресенье 19:00 МСК — личный отчёт участнику раз в 2 недели."""
    now = datetime.now(timezone.utc)
    sent_keys: set[str] = set()

    async with get_session_factory()() as session:
        rows = await _get_active_participants(session)
        for participant, user in rows:
            level = participant.level
            week = participant.week

            if week % 2 != 0:
                continue

            key = f"{user.id}_{level}_{week}"
            if key in sent_keys:
                continue
            sent_keys.add(key)

            first = (user.name or "Брат").split()[0]
            total = LEVEL_WEEKS.get(level, 8)
            pct = round(week / total * 100)

            days_str = ""
            if participant.activated_at:
                try:
                    act = participant.activated_at
                    act = act.replace(tzinfo=timezone.utc) if act.tzinfo is None else act
                    days_in = (now - act).days
                    days_str = f"📅 *Дней в программе:* {days_in}\n"
                except Exception:
                    pass

            w2 = max(1, week - 1)
            w1 = max(1, week - 2)

            sep = "&" if "?" in miniapp_url else "?"
            miniapp_link = f"{miniapp_url}{sep}lvl={level}&wk={week}"

            try:
                await bot.send_message(
                    chat_id=user.id,
                    parse_mode="Markdown",
                    text=(
                        f"📊 *Зеркало прогресса — {first}*\n\n"
                        f"{days_str}"
                        f"📈 *Прогресс:* Шаг {week} из {total} ({pct}%)\n"
                        f"🎯 *Программа:* {LEVEL_NAMES.get(level, level)}\n\n"
                        "Продолжай — каждый шаг считается. 🌱\n"
                        "_БаракАллах фикум!_"
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "📱 Открыть карту пути",
                            web_app=WebAppInfo(url=miniapp_link),
                        ),
                    ]]),
                )
            except Exception as e:
                logger.warning("progress_mirror → %s: %s", user.id, e)


async def job_check_payments(bot, config):
    """Каждые 2 минуты проверяем pending-платежи в ЮKassa и активируем оплативших."""
    from datetime import timezone
    from bot_v2.db.engine import get_session_factory
    from bot_v2.db.models import Payment, User
    from bot_v2.db.repositories.participant import ParticipantRepo
    from bot_v2.handlers.payments import TARIFF_LEVEL_MAP
    from bot_v2.services.yookassa_svc import get_payment_status
    from bot_v2.services.mizan_os import notify_mizan_payment
    from bot_v2.services.i18n import t
    from bot_v2.services.program import get_tariff_view
    from sqlalchemy import select
    import datetime as _dt

    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        return

    async with get_session_factory()() as session:
        async with session.begin():
            # Берём pending-платежи не старше 24 часов
            cutoff = _dt.datetime.now(timezone.utc) - _dt.timedelta(hours=24)
            result = await session.execute(
                select(Payment).where(
                    Payment.status == "pending",
                    Payment.yoo_payment_id.isnot(None),
                    Payment.created_at >= cutoff,
                )
            )
            pending = result.scalars().all()

        for payment in pending:
            yoo_id = payment.yoo_payment_id
            if not yoo_id:
                continue
            status = await get_payment_status(
                config.yookassa_shop_id, config.yookassa_secret_key, yoo_id
            )

            if status == "succeeded":
                async with get_session_factory()() as session:
                    async with session.begin():
                        # Помечаем оплаченным
                        db_pay = await session.get(Payment, payment.id)
                        if not db_pay or db_pay.status == "paid":
                            continue
                        db_pay.status = "paid"
                        db_pay.paid_at = _dt.datetime.now(timezone.utc)

                        user = await session.get(User, payment.user_id)
                        lang = user.language_code if user else "ru"
                        tariff_view = get_tariff_view(payment.tariff_id, lang)
                        tariff_name = tariff_view["name"] if tariff_view else payment.tariff_id

                        # Активируем участника
                        level = TARIFF_LEVEL_MAP.get(payment.tariff_id)
                        if level:
                            p_repo = ParticipantRepo(session)
                            participant = await p_repo.activate(payment.user_id, level=level, week=1)
                            await session.flush()

                            # Для Старта (vakt) — сначала диагностика уровня, потом урок
                            if payment.tariff_id == "vakt":
                                from bot_v2.db.repositories import SettingsRepo as _SR
                                await _SR(session).set(f"gift_pending:{payment.user_id}", "1")
                                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                                kb = InlineKeyboardMarkup(inline_keyboard=[[
                                    InlineKeyboardButton(text="🎯 Пройти диагностику уровня", callback_data="start_diag")
                                ]])
                                try:
                                    await bot.send_message(
                                        chat_id=payment.user_id,
                                        text=(
                                            f"✅ *Оплата подтверждена!*\n\n"
                                            f"📦 {tariff_name}\n\n"
                                            f"Прежде чем начать — пройди короткую диагностику (2 минуты).\n"
                                            f"Это 8 вопросов, чтобы я подобрал тебе уроки по твоему уровню. 🌱"
                                        ),
                                        parse_mode="Markdown",
                                        reply_markup=kb,
                                    )
                                except Exception as e:
                                    logger.warning("payment diag prompt failed %s: %s", payment.user_id, e)
                            else:
                                # Для остальных тарифов — сразу урок
                                try:
                                    await bot.send_message(
                                        chat_id=payment.user_id,
                                        text=(
                                            f"✅ *Оплата подтверждена!*\n\n"
                                            f"📦 {tariff_name}\n\n"
                                            f"Добро пожаловать в программу! Сейчас пришлю первый урок 🌱"
                                        ),
                                        parse_mode="Markdown",
                                    )
                                except Exception as e:
                                    logger.warning("payment confirm msg failed %s: %s", payment.user_id, e)

                                from bot_v2.handlers.program import send_weekly_lesson
                                try:
                                    await send_weekly_lesson(bot, payment.user_id, participant, session, config)
                                except Exception as e:
                                    logger.warning("send_weekly_lesson after payment failed %s: %s", payment.user_id, e)

                            # Уведомляем кураторов
                            name = user.name if user else str(payment.user_id)
                            username = user.username if user and user.username else ""
                            await notify_mizan_payment(
                                config,
                                payment_id=yoo_id,
                                telegram_user_id=payment.user_id,
                                amount=payment.amount,
                                tariff_id=payment.tariff_id,
                                product_name=tariff_name,
                                customer_name=name,
                                telegram_username=username,
                                participant_activated=True,
                                paid_at=db_pay.paid_at,
                            )
                            for cid in (config.curator_ids or []):
                                try:
                                    await bot.send_message(
                                        chat_id=cid,
                                        text=(
                                            f"💳 *Оплата получена!*\n\n"
                                            f"👤 {name} (`{payment.user_id}`)\n"
                                            f"📦 {tariff_name}\n"
                                            f"💰 {payment.amount:,} ₽\n"
                                            f"✅ Участник активирован автоматически"
                                        ).replace(",", " "),
                                        parse_mode="Markdown",
                                    )
                                except Exception:
                                    pass

            elif status == "canceled":
                async with get_session_factory()() as session:
                    async with session.begin():
                        db_pay = await session.get(Payment, payment.id)
                        if db_pay:
                            db_pay.status = "failed"


async def job_check_followups(bot):
    """Каждые 30 минут — отправляем follow-up тем, у кого наступило время."""
    import time as _time
    from bot_v2.db.engine import get_session_factory
    from bot_v2.db.repositories import SettingsRepo

    now = int(_time.time())

    try:
        async with get_session_factory()() as session:
            async with session.begin():
                from sqlalchemy import text
                result = await session.execute(
                    text("SELECT key, value FROM bot_settings WHERE key LIKE 'followup_at:%'")
                )
                rows = result.fetchall()
    except Exception as _e:
        logger.warning("job_check_followups: settings table unavailable: %s", _e)
        return

    for key, value in rows:
        try:
            fire_at = int(value)
        except ValueError:
            continue
        if now < fire_at:
            continue

        uid = int(key.split(":")[1])

        # Удаляем запись и отправляем сообщение
        async with get_session_factory()() as session:
            async with session.begin():
                repo = SettingsRepo(session)
                await repo.set(key, "sent")  # помечаем чтобы не слать повторно

        if value == "sent":
            continue

        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            await bot.send_message(
                uid,
                "Ас-саляму алейкум 🌙\n\n"
                "Вчера ты прошёл диагностику.\n\n"
                "Один честный вопрос — что тебя остановило?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💸 Цена", callback_data="kb_fu_price")],
                    [InlineKeyboardButton(text="⏰ Нет времени сейчас", callback_data="kb_fu_time")],
                    [InlineKeyboardButton(text="🤔 Не уверен, что поможет", callback_data="kb_fu_unsure")],
                    [InlineKeyboardButton(text="✅ Уже оплатил — спасибо!", callback_data="kb_fu_paid")],
                ]),
            )
            logger.info("Follow-up sent to %s", uid)
        except Exception as e:
            logger.warning("Follow-up failed for %s: %s", uid, e)
