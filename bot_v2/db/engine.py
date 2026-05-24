from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import inspect, text

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
        await conn.run_sync(_ensure_compat_columns)


def _ensure_compat_columns(sync_conn):
    inspector = inspect(sync_conn)
    if "users" not in inspector.get_table_names():
        return

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "language_code" not in user_columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN language_code VARCHAR(8) NOT NULL DEFAULT 'ru'"))


async def close_db():
    if _engine:
        await _engine.dispose()
