import os
from dataclasses import dataclass, field


@dataclass
class Config:
    bot_token: str
    database_url: str
    curator_ids: list[int]

    site: str = "https://iq-barakah.ru"
    miniapp_url: str = "https://rashidd1987.github.io/iq-barakah/miniapp.html"
    ship_url: str = "https://rashidd1987.github.io/iq-barakah/ship_barakat_business.html"

    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    payments_provider_token: str = ""

    anthropic_api_key: str = ""

    default_call_link: str = "https://t.me/iqbarakah"


def load_config() -> Config:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан")

    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/iqbarakah")

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
