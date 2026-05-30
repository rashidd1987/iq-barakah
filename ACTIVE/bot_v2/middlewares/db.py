from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.engine import get_session_factory
from bot_v2.db.models import Participant


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session_factory = get_session_factory()
        async with session_factory() as session:
            async with session.begin():
                data["session"] = session
                result = await handler(event, data)
                # Обновляем last_active для любого события от реального пользователя
                try:
                    user_id = _extract_user_id(event)
                    if user_id:
                        await _touch_last_active(session, user_id)
                except Exception:
                    pass
                return result


def _extract_user_id(event: TelegramObject) -> int | None:
    if isinstance(event, Update):
        msg = event.message or event.callback_query
        if msg:
            user = getattr(msg, "from_user", None)
            return user.id if user else None
    return None


async def _touch_last_active(session: AsyncSession, user_id: int):
    result = await session.execute(
        select(Participant).where(
            Participant.user_id == user_id,
            Participant.is_active == True,
        )
    )
    p = result.scalar_one_or_none()
    if p:
        p.last_active = datetime.now(timezone.utc)
