from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot_v2.db.models import Participant, User


class ParticipantRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> Participant | None:
        result = await self.session.execute(
            select(Participant).where(Participant.user_id == user_id, Participant.is_active == True)
        )
        return result.scalar_one_or_none()

    async def activate(self, user_id: int, level: str, week: int = 1, vakt_level: str | None = None) -> Participant:
        existing = await self.get(user_id)
        if existing:
            existing.level = level
            existing.week = week
            existing.vakt_level = vakt_level
            existing.activated_at = datetime.now(timezone.utc)
            existing.graduated_at = None
            existing.is_active = True
        else:
            existing = Participant(
                user_id=user_id, level=level, week=week,
                vakt_level=vakt_level,
                activated_at=datetime.now(timezone.utc),
            )
            self.session.add(existing)
        await self.session.flush()
        return existing

    async def advance_week(self, user_id: int) -> Participant | None:
        p = await self.get(user_id)
        if p:
            p.week += 1
            await self.session.flush()
        return p

    async def graduate(self, user_id: int):
        p = await self.get(user_id)
        if p:
            p.graduated_at = datetime.now(timezone.utc)
            p.is_active = False
            await self.session.flush()

    async def deactivate(self, user_id: int):
        p = await self.get(user_id)
        if p:
            p.is_active = False
            await self.session.flush()

    async def all_active(self) -> list[Participant]:
        result = await self.session.execute(
            select(Participant)
            .options(selectinload(Participant.user))
            .where(Participant.is_active == True)
        )
        return list(result.scalars())
