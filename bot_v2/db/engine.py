from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

_engine = None
_session_factory = None


def setup_db(database_url: str):
    global _engine, _session_factory
    _engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


def get_session_factory() -> async_sessionmaker:
    return _session_factory


async def create_tables():
    from bot_v2.db.base import Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    if _engine:
        await _engine.dispose()
