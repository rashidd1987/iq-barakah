import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_ids: frozenset[int]
    github_owner: str
    github_token: str
    request_timeout_seconds: float
    port: int


def load_config() -> Config:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    raw_owner_ids = os.environ.get("OWNER_TELEGRAM_IDS", "").strip()
    if not raw_owner_ids:
        raise RuntimeError("OWNER_TELEGRAM_IDS is required")

    try:
        owner_ids = frozenset(
            int(value.strip()) for value in raw_owner_ids.split(",") if value.strip()
        )
    except ValueError as exc:
        raise RuntimeError("OWNER_TELEGRAM_IDS must contain numeric Telegram IDs") from exc

    if not owner_ids:
        raise RuntimeError("OWNER_TELEGRAM_IDS must not be empty")

    return Config(
        bot_token=bot_token,
        owner_ids=owner_ids,
        github_owner=os.environ.get("GITHUB_OWNER", "rashidd1987").strip(),
        github_token=os.environ.get("GITHUB_READ_TOKEN", "").strip(),
        request_timeout_seconds=float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10")),
        port=int(os.environ.get("PORT", "8080")),
    )
