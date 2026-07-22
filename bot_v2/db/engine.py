import logging
import os
import re

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


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
    await _grant_pwa_database_access()


async def _grant_pwa_database_access():
    """Grant the separate PWA API role only the shared-program access it needs.

    Disabled unless PWA_DB_ROLE is explicitly configured. Grant failures are
    logged but never prevent the Telegram bot from starting.
    """
    role = os.environ.get("PWA_DB_ROLE", "").strip()
    if not role:
        return
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", role):
        logger.error("PWA_DB_ROLE has an invalid identifier; grants skipped")
        return

    quoted_role = '"' + role.replace('"', '""') + '"'
    shared_permissions = {
        "users": "SELECT",
        "participants": "SELECT, UPDATE",
        "tracker_records": "SELECT, INSERT, UPDATE",
        "week_acks": "SELECT, INSERT, UPDATE",
        "wheel_records": "SELECT, INSERT, UPDATE",
        "muhasaba_logs": "SELECT, INSERT, UPDATE",
    }
    try:
        async with _engine.begin() as conn:
            database = await conn.scalar(text("SELECT current_database()"))
            quoted_database = '"' + database.replace('"', '""') + '"'
            await conn.execute(text(f"GRANT CONNECT ON DATABASE {quoted_database} TO {quoted_role}"))
            await conn.execute(text(f"GRANT USAGE, CREATE ON SCHEMA public TO {quoted_role}"))

            existing = set((await conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            ))).scalars())
            for table, permissions in shared_permissions.items():
                if table in existing:
                    await conn.execute(text(
                        f'GRANT {permissions} ON TABLE "{table}" TO {quoted_role}'
                    ))
            await conn.execute(text(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted_role}"
            ))
        logger.info("PWA database access granted to configured role")
    except Exception:
        logger.exception("Could not grant PWA database access; bot startup will continue")


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
