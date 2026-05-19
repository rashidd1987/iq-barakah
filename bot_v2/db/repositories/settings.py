from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import BotSetting, LessonMedia, Pair


class SettingsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str, default: str | None = None) -> str | None:
        row = await self.session.get(BotSetting, key)
        return row.value if row else default

    async def set(self, key: str, value: str):
        stmt = insert(BotSetting).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value})
        await self.session.execute(stmt)
        await self.session.flush()


class LessonMediaRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, level: str, week: int, media_type: str) -> str | None:
        result = await self.session.execute(
            select(LessonMedia).where(
                LessonMedia.level == level,
                LessonMedia.week == week,
                LessonMedia.media_type == media_type,
            )
        )
        row = result.scalar_one_or_none()
        return row.value if row else None

    async def set(self, level: str, week: int, media_type: str, value: str, set_by: int | None = None):
        stmt = insert(LessonMedia).values(
            level=level, week=week, media_type=media_type, value=value, set_by=set_by
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_lesson_media",
            set_={"value": value, "set_by": set_by},
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def all(self) -> list[LessonMedia]:
        result = await self.session.execute(select(LessonMedia).order_by(LessonMedia.level, LessonMedia.week))
        return list(result.scalars())


class PairRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_partner(self, user_id: int) -> int | None:
        result = await self.session.execute(
            select(Pair).where(
                ((Pair.uid1 == user_id) | (Pair.uid2 == user_id)),
                Pair.dissolved_at == None,
            )
        )
        pair = result.scalar_one_or_none()
        if not pair:
            return None
        return pair.uid2 if pair.uid1 == user_id else pair.uid1

    async def paired_ids(self) -> set[int]:
        result = await self.session.execute(select(Pair).where(Pair.dissolved_at == None))
        pairs = result.scalars().all()
        ids: set[int] = set()
        for p in pairs:
            ids.add(p.uid1)
            ids.add(p.uid2)
        return ids

    async def create_pair(self, uid1: int, uid2: int) -> Pair:
        pair = Pair(uid1=min(uid1, uid2), uid2=max(uid1, uid2))
        self.session.add(pair)
        await self.session.flush()
        return pair
