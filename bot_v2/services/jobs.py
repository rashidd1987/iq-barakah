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

FAJR_MSGS = [
    (
        "🌅 *Ас-саляму алейкум!*\n\n"
        "Фаджр — якорь дня. Тот, кто поднимается на рассвете — "
        "контролирует своё утро, а утро задаёт весь день.\n\n"
        "_Один намаз — и ты уже победил себя. БаракАллах фикум 🌿_"
    ),
    (
        "🌙 *Ещё темно — но Аллах уже видит тебя.*\n\n"
        "Эти минуты до рассвета — самые ценные в сутках. "
        "Фаджр — это не просто намаз, это состояние.\n\n"
        "_Вставай и начинай свой день с Аллаха. 🌿_"
    ),
    (
        "⭐ *Рассвет близко...*\n\n"
        "Помнишь? «Маленькое и постоянное — лучше большого и временного». "
        "Один тихий намаз на рассвете — это и есть система.\n\n"
        "_Да примет Аллах наш Фаджр. Ин ша Аллах 🌿_"
    ),
]

FRIDAY_MSGS = [
    (
        "🕌 *Джума мубарак!*\n\n"
        "Один вопрос от Джарваса на эту пятницу:\n\n"
        "_Что на этой неделе ты сделал ради Аллаха — не ради результата, а ради Него?_\n\n"
        "Запиши ответ — даже одно слово. Это и есть мухасаба. 🌿"
    ),
    (
        "🌙 *Баракатной пятницы!*\n\n"
        "Пятница — день рефлексии и благодарности. "
        "Что из инструментов программы зацепило тебя на этой неделе?\n\n"
        "_Даже маленькое и постоянное — уже победа. БаракАллах фикум 🌿_"
    ),
    (
        "⭐ *Пятничное послание от Джарваса:*\n\n"
        "Мы собираемся вместе в IQ Barakah каждую неделю — "
        "как умма собирается на Джуму.\n\n"
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
                await bot.send_message(
                    chat_id=user.id,
                    text=random.choice(FAJR_MSGS),
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
                                f"📊 Уровень {participant.level} · Неделя {participant.week}\n\n"
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
                        f"📈 *Прогресс:* Неделя {week} из {total} ({pct}%)\n"
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
