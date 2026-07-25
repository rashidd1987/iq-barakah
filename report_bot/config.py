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
    data_dir: str
    monitor_interval_seconds: int
    evening_report_hour: int
    timezone: str


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

    monitor_interval = int(os.environ.get("MONITOR_INTERVAL_SECONDS", "300"))
    report_hour = int(os.environ.get("EVENING_REPORT_HOUR", "21"))
    if monitor_interval < 60:
        raise RuntimeError("MONITOR_INTERVAL_SECONDS must be at least 60")
    if not 0 <= report_hour <= 23:
        raise RuntimeError("EVENING_REPORT_HOUR must be between 0 and 23")

    return Config(
        bot_token=bot_token,
        owner_ids=owner_ids,
        github_owner=os.environ.get("GITHUB_OWNER", "rashidd1987").strip(),
        github_token=os.environ.get("GITHUB_READ_TOKEN", "").strip(),
        request_timeout_seconds=float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10")),
        port=int(os.environ.get("PORT", "8080")),
        data_dir=os.environ.get("REPORT_BOT_DATA_DIR", "/data").strip() or "/data",
        monitor_interval_seconds=monitor_interval,
        evening_report_hour=report_hour,
        timezone=os.environ.get("REPORT_TIMEZONE", "Europe/Moscow").strip(),
    )
