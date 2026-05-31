import os
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass
class Config:
    bot_token: str
    database_url: str
    curator_ids: list[int]

    site: str = "https://iq-barakah.ru"
    miniapp_url: str = "https://iq-barakah.ru/miniapp.html"
    ship_url: str = "https://iq-barakah.ru/ship_barakat_business.html"

    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    payments_provider_token: str = ""

    anthropic_api_key: str = ""

    default_call_link: str = "https://t.me/iqbarakah"
    version: str = "bot_v2.20260531.6"


def load_config() -> Config:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан")

    db_url = _load_database_url()

    curator_env = os.environ.get("CURATOR_ID", "140700248")
    curators = [int(x.strip()) for x in curator_env.split(",") if x.strip()]

    return Config(
        bot_token=token,
        database_url=db_url,
        curator_ids=curators,
        yookassa_shop_id=os.environ.get("YOOKASSA_SHOP_ID", ""),
        yookassa_secret_key=os.environ.get("YOOKASSA_SECRET_KEY", ""),
        payments_provider_token=os.environ.get("PAYMENTS_TOKEN", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )


def _load_database_url() -> str:
    raw = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("POSTGRESQL_URL")
    )
    if raw:
        return _normalize_database_url(raw)

    host = os.environ.get("PGHOST") or os.environ.get("DB_HOST")
    user = os.environ.get("PGUSER") or os.environ.get("DB_USER")
    password = os.environ.get("PGPASSWORD") or os.environ.get("DB_PASSWORD")
    db = os.environ.get("PGDATABASE") or os.environ.get("DB_NAME")
    port = os.environ.get("PGPORT") or os.environ.get("DB_PORT") or "5432"

    if host and user and password and db:
        return (
            f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(password)}"
            f"@{host}:{port}/{quote_plus(db)}"
        )

    raise RuntimeError(
        "DATABASE_URL не задан. Добавь переменную вида "
        "postgresql+asyncpg://user:password@host:5432/dbname"
    )


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    return url
