import logging
import re

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None

_ROLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_PWA_SUPPORT_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS pwa_users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        tg_id BIGINT UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pwa_tracker (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
        date DATE NOT NULL,
        data JSONB NOT NULL DEFAULT '{}',
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(user_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pwa_wheel (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
        scores JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pwa_ship (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES pwa_users(id) ON DELETE CASCADE,
        type TEXT NOT NULL,
        scores JSONB NOT NULL DEFAULT '{}',
        avg FLOAT NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pwa_analytics (
        id BIGSERIAL PRIMARY KEY,
        uid TEXT NOT NULL,
        event TEXT NOT NULL,
        screen TEXT,
        ts TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pwa_tg_sessions (
        session_id TEXT PRIMARY KEY,
        tg_id BIGINT,
        tg_name TEXT,
        confirmed BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS push_tokens (
        user_id BIGINT PRIMARY KEY,
        expo_token TEXT NOT NULL,
        platform TEXT NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pwa_tracker_user_date ON pwa_tracker(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_pwa_wheel_user ON pwa_wheel(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_pwa_ship_user ON pwa_ship(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_pwa_analytics_uid ON pwa_analytics(uid)",
)

_PWA_READ_TABLES = (
    "users",
    "participants",
    "week_acks",
    "task_completions",
    "tracker_records",
    "wheel_records",
    "muhasaba_logs",
    "diag_results",
    "bot_payments",
)

_PWA_INSERT_UPDATE_TABLES = (
    "week_acks",
    "tracker_records",
    "wheel_records",
    "muhasaba_logs",
    "push_tokens",
)

_PWA_OWNED_DATA_TABLES = (
    "pwa_users",
    "pwa_tracker",
    "pwa_wheel",
    "pwa_ship",
    "pwa_analytics",
    "pwa_tg_sessions",
)


def setup_db(database_url: str):
    global _engine, _session_factory
    _engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


def get_session_factory() -> async_sessionmaker:
    return _session_factory


async def ensure_database(database_url: str):
    url = make_url(database_url)
    database = url.database
    if not database or database in {"postgres", "template1"}:
        return

    maintenance_url = url.set(database="postgres")
    maintenance_engine = create_async_engine(
        maintenance_url,
        echo=False,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with maintenance_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :database"),
                {"database": database},
            )
            if exists:
                return

            quoted_database = '"' + database.replace('"', '""') + '"'
            await conn.execute(text(f"CREATE DATABASE {quoted_database}"))
            logger.info("Created PostgreSQL database %s", database)
    finally:
        await maintenance_engine.dispose()


async def create_tables():
    from bot_v2.db.base import Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_compat_columns)


def _quote_identifier(value: str) -> str:
    if not _ROLE_NAME_RE.fullmatch(value):
        raise ValueError("Database role name contains unsupported characters")
    return f'"{value}"'


async def ensure_pwa_database_access(role_name: str) -> None:
    """Grant the existing PWA role least-privilege access to the bot database."""
    if _engine is None:
        raise RuntimeError("Database engine is not initialized")

    quoted_role = _quote_identifier(role_name)
    async with _engine.begin() as conn:
        current_database = await conn.scalar(text("SELECT current_database()"))
        quoted_database = _quote_identifier(current_database)

        for statement in _PWA_SUPPORT_TABLES:
            await conn.execute(text(statement))

        await conn.execute(
            text(f"GRANT CONNECT ON DATABASE {quoted_database} TO {quoted_role}")
        )
        await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {quoted_role}"))

        read_tables = ", ".join(_PWA_READ_TABLES)
        insert_update_tables = ", ".join(_PWA_INSERT_UPDATE_TABLES)
        owned_data_tables = ", ".join(_PWA_OWNED_DATA_TABLES)
        await conn.execute(
            text(f"GRANT SELECT ON TABLE {read_tables} TO {quoted_role}")
        )
        await conn.execute(
            text(
                "GRANT INSERT, UPDATE "
                f"ON TABLE {insert_update_tables} TO {quoted_role}"
            )
        )
        await conn.execute(
            text(
                "GRANT UPDATE ON TABLE users, participants "
                f"TO {quoted_role}"
            )
        )
        await conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                f"ON TABLE {owned_data_tables} TO {quoted_role}"
            )
        )
        await conn.execute(
            text(
                "GRANT USAGE, SELECT ON ALL SEQUENCES "
                f"IN SCHEMA public TO {quoted_role}"
            )
        )


def _ensure_compat_columns(sync_conn):
    inspector = inspect(sync_conn)
    if "users" not in inspector.get_table_names():
        return

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "language_code" not in user_columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN language_code VARCHAR(8) NOT NULL DEFAULT 'ru'"))

    if "participants" in inspector.get_table_names():
        p_columns = {col["name"] for col in inspector.get_columns("participants")}
        if "last_active" not in p_columns:
            sync_conn.execute(text("ALTER TABLE participants ADD COLUMN last_active TIMESTAMP WITH TIME ZONE"))

    # UTM-атрибуция
    if "utm_source" not in user_columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN utm_source VARCHAR(256)"))
    if "last_utm_source" not in user_columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN last_utm_source VARCHAR(256)"))

    # Баракаты
    if "referral_code" not in user_columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN referral_code VARCHAR(32)"))
        sync_conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_referral_code ON users(referral_code)"))
    if "referred_by" not in user_columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN referred_by BIGINT REFERENCES users(id)"))
    if "barakah_balance" not in user_columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN barakah_balance INTEGER NOT NULL DEFAULT 0"))
    if "charity_consent" not in user_columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN charity_consent BOOLEAN NOT NULL DEFAULT false"))

    # Таблица транзакций Баракатов
    existing_tables = inspector.get_table_names()
    if "barakah_transactions" not in existing_tables:
        sync_conn.execute(text("""
            CREATE TABLE barakah_transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id),
                amount INTEGER NOT NULL,
                kind VARCHAR(32) NOT NULL,
                ref_user_id BIGINT,
                payment_id INTEGER REFERENCES bot_payments(id),
                note VARCHAR(256),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
            )
        """))


async def close_db():
    if _engine:
        await _engine.dispose()
