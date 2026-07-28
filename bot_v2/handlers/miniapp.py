"""Хендлер WebApp-данных из Mini App (трекер, колесо баланса, задания)."""
import json
import logging
from datetime import date

from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.config import Config
from bot_v2.db.models import Participant, TaskCompletion, TrackerRecord, User, WheelRecord
from bot_v2.services.program import LEVEL_NAMES, LEVEL_WEEKS
from bot_v2.services.program_content import PROGRAM

logger = logging.getLogger(__name__)
router = Router(name="miniapp")


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message, session: AsyncSession, bot=None, config: Config = None):
    try:
        payload = json.loads(message.web_app_data.data)
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Invalid WebApp data from %s", message.from_user.id)
        return

    action = payload.get("action")
    uid = message.from_user.id

    if action == "save_tracker":
        await _save_tracker(session, uid, payload)
    elif action == "save_wheel":
        await _save_wheel(session, uid, payload)
    elif action == "check_task":
        await _check_task(session, uid, payload, bot, config)
    elif action == "open_lesson":
        await _send_full_lesson(session, uid, payload, message)
    elif action == "curator_report":
        await _send_curator_report(session, uid, payload, message, bot, config)
    elif action == "get_balance":
        await _send_balance(session, uid, message)
    else:
        logger.debug("Unknown WebApp action: %s", action)


async def _save_tracker(session: AsyncSession, user_id: int, payload: dict):
    today = date.today()
    habits = payload.get("habits", {})

    stmt = insert(TrackerRecord).values(user_id=user_id, date=today, habits=habits)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_tracker_day",
        set_={"habits": habits},
    )
    await session.execute(stmt)


async def _save_wheel(session: AsyncSession, user_id: int, payload: dict):
    scores = payload.get("scores", {})
    record = WheelRecord(user_id=user_id, scores=scores)
    session.add(record)


async def _check_task(session: AsyncSession, user_id: int, payload: dict, bot, config):
    """Отметить задание выполненным/невыполненным. Уведомить куратора при 100%."""
    level = payload.get("level")
    week = payload.get("week")
    task_index = payload.get("task_index")
    checked = payload.get("checked", True)
    total_tasks = payload.get("total_tasks", 0)

    if not all([level, week is not None, task_index is not None]):
        logger.warning("check_task: missing fields from %s: %s", user_id, payload)
        return

    if checked:
        stmt = insert(TaskCompletion).values(
            user_id=user_id, level=level, week=week, task_index=task_index
        ).on_conflict_do_nothing(constraint="uq_task_completion")
        await session.execute(stmt)
    else:
        stmt = delete(TaskCompletion).where(
            TaskCompletion.user_id == user_id,
            TaskCompletion.level == level,
            TaskCompletion.week == week,
            TaskCompletion.task_index == task_index,
        )
        await session.execute(stmt)

    # Check if all tasks done this week
    if checked and total_tasks > 0:
        done_count_q = await session.execute(
            select(TaskCompletion).where(
                TaskCompletion.user_id == user_id,
                TaskCompletion.level == level,
                TaskCompletion.week == week,
            )
        )
        done_count = len(done_count_q.scalars().all())

        if done_count >= total_tasks:
            await _notify_all_tasks_done(session, user_id, level, week, bot, config)


async def _notify_all_tasks_done(session: AsyncSession, user_id: int, level: str, week: int, bot, config):
    """Уведомить куратора что участник выполнил все задания недели."""
    if not bot or not config:
        return

    user = await session.get(User, user_id)
    name = (user.name if user else None) or "Участник"
    username = f"@{user.username}" if user and user.username else f"id:{user_id}"

    level_name = LEVEL_NAMES.get(level, level)
    text = (
        f"✅ *Все задания выполнены*\n\n"
        f"👤 {name} ({username})\n"
        f"📍 {level_name} · Шаг {week}\n\n"
        f"Участник выполнил все задания текущей недели в Mini App."
    )

    for cid in (config.curator_ids or []):
        try:
            await bot.send_message(chat_id=cid, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.warning("Cannot notify curator %s: %s", cid, e)


async def _send_curator_report(session: AsyncSession, user_id: int, payload: dict, message: Message, bot, config):
    """Участник отправляет отчёт куратору из Mini App."""
    user = await session.get(User, user_id)
    name = (user.name if user else None) or "Участник"
    username = f"@{user.username}" if user and user.username else f"id:{user_id}"

    level = payload.get("level", "")
    week = payload.get("week", 0)
    habits_done = payload.get("habitsDone", 0)
    habits_total = payload.get("habitsTotal", 0)
    tasks_done = payload.get("tasksDone", 0)
    tasks_total = payload.get("tasksTotal", 0)
    streak = payload.get("streak", 0)
    user_message = payload.get("message", "").strip()

    level_name = LEVEL_NAMES.get(level, level) if level else "—"

    habits_bar = "🟩" * habits_done + "⬜" * max(0, habits_total - habits_done)
    tasks_bar = "✅" * tasks_done + "⬜" * max(0, tasks_total - tasks_done)

    text = (
        f"📊 *Отчёт участника*\n\n"
        f"👤 {name} ({username})\n"
        f"📍 {level_name} · Шаг {week}\n"
        f"🔥 Стрик: {streak} дн.\n\n"
        f"*Привычки сегодня:* {habits_done}/{habits_total}\n{habits_bar}\n\n"
        f"*Задания недели:* {tasks_done}/{tasks_total}\n{tasks_bar}"
    )
    if user_message:
        text += f"\n\n💬 *Сообщение:* {user_message}"

    # Notify curators
    if bot and config:
        for cid in (config.curator_ids or []):
            try:
                await bot.send_message(chat_id=cid, text=text, parse_mode="Markdown")
            except Exception as e:
                logger.warning("Cannot send curator report to %s: %s", cid, e)

    # Confirm to user
    await message.answer(
        "✅ Отчёт отправлен куратору! Альхамдулиллях 🌿\n\nПродолжай в том же духе — ты молодец.",
        parse_mode="Markdown"
    )


async def _send_full_lesson(session: AsyncSession, user_id: int, payload: dict, message: Message):
    """Отправить полный урок из бота когда студент нажимает 'Полный урок в боте'."""
    level = payload.get("level")
    week = payload.get("week")

    if not level or not week:
        logger.warning("open_lesson: missing level/week from %s", user_id)
        return

    lessons = PROGRAM.get(level, [])
    week_idx = int(week) - 1
    if week_idx < 0 or week_idx >= len(lessons):
        logger.warning("open_lesson: week %s out of range for level %s", week, level)
        return

    # Get skill level from participant record
    result = await session.execute(select(Participant).where(Participant.user_id == user_id))
    participant = result.scalar_one_or_none()
    skill_level = (participant.vakt_level or "I") if participant else "I"

    lesson = lessons[week_idx]
    title = lesson.get("title", f"Шаг {week}")
    hadith = lesson.get("hadith", "")

    raw_text = lesson.get("text", "")
    if isinstance(raw_text, dict):
        text_body = raw_text.get(skill_level, raw_text.get("I", ""))
    else:
        text_body = raw_text

    raw_tasks = lesson.get("tasks", [])
    if isinstance(raw_tasks, dict):
        tasks_list = raw_tasks.get(skill_level, raw_tasks.get("I", []))
    else:
        tasks_list = raw_tasks
    tasks_str = "\n".join(f"  {t}" for t in tasks_list)

    level_name = LEVEL_NAMES.get(level, level)
    lesson_text = (
        f"*{title}*\n"
        f"_{level_name}_\n\n"
        f"📜 _{hadith}_\n\n"
        f"{text_body}\n\n"
        f"*Задания на эту неделю:*\n{tasks_str}"
    )

    if len(lesson_text) > 4096:
        lesson_text = lesson_text[:4090] + "…"

    try:
        await message.answer(lesson_text, parse_mode="Markdown")
    except Exception:
        plain = lesson_text.replace("*", "").replace("_", "")
        try:
            await message.answer(plain)
        except Exception as e:
            logger.warning("Cannot send full lesson to %s: %s", user_id, e)


async def _send_balance(session: AsyncSession, user_id: int, message: Message):
    """Отправить баланс Баракатов из мини-апп."""
    from bot_v2.db.models import User
    from bot_v2.services.barakah import get_transactions, get_referral_count, ensure_referral_code
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    user = await session.get(User, user_id)
    if not user:
        return

    ref_count = await get_referral_count(session, user_id)
    code = await ensure_referral_code(session, user)
    bot_me = await message.bot.get_me()
    link = f"https://t.me/{bot_me.username}?start=ref_{code}"

    transactions = await get_transactions(session, user_id, limit=5)
    kind_labels = {"referral": "🎁 Реферал", "spend": "💸 Оплата", "donate": "🤲 Донат", "expire": "⏳ Истекло"}
    history = ""
    if transactions:
        lines = [f"{kind_labels.get(tx.kind, tx.kind)}: {'+'if tx.amount>0 else ''}{tx.amount} Б" for tx in transactions]
        history = "\n\n*Последние операции:*\n" + "\n".join(lines)

    text = (
        f"💰 *Баланс Баракатов: {user.barakah_balance} Б*\n\n"
        f"1 Баракат = 1 ₽\n"
        f"👥 Приглашено друзей: {ref_count}{history}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Пригласить друга", url=f"https://t.me/share/url?url={link}")],
        [InlineKeyboardButton(text="🤲 Задонатить", callback_data="barakah_donate")],
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)
