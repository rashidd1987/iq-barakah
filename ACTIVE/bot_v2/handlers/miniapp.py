"""Хендлер WebApp-данных из Mini App (трекер, колесо баланса)."""
import json
import logging
from datetime import date

from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import TrackerRecord, WheelRecord

logger = logging.getLogger(__name__)
router = Router(name="miniapp")


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message, session: AsyncSession):
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
