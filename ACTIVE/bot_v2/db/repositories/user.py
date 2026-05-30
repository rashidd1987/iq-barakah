from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_or_create(
        self,
        user_id: int,
        name: str,
        username: str | None = None,
        language_code: str = "ru",
    ) -> tuple[User, bool]:
        user = await self.get(user_id)
        if user:
            changed = False
            if username and user.username != username:
                user.username = username
                changed = True
            if changed:
                await self.session.flush()
            return user, False
        user = User(id=user_id, name=name, username=username, language_code=language_code)
        self.session.add(user)
        await self.session.flush()
        return user, True

    async def update(self, user_id: int, **kwargs) -> User | None:
        user = await self.get(user_id)
        if not user:
            return None
        for k, v in kwargs.items():
            setattr(user, k, v)
        await self.session.flush()
        return user

    async def set_pd_consent(self, user_id: int):
        user = await self.get(user_id)
        if user:
            user.pd_consent_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def all_ids(self) -> list[int]:
        result = await self.session.execute(select(User.id))
        return list(result.scalars())
