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
        f"📍 {level_name} · Неделя {week}\n\n"
        f"Участник выполнил все задания текущей недели в Mini App."
    )

    for cid in (config.curator_ids or []):
        try:
            await bot.send_message(chat_id=cid, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.warning("Cannot notify curator %s: %s", cid, e)
