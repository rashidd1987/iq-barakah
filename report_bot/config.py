import os
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class AIProviderSecrets:
    openai: str = field(repr=False)
    anthropic: str = field(repr=False)
    gemini: str = field(repr=False)
    perplexity: str = field(repr=False)
    xai: str = field(repr=False)
    deepseek: str = field(repr=False)
    kimi: str = field(repr=False)

    def configured_providers(self) -> tuple[str, ...]:
        providers = (
            ("openai", self.openai),
            ("anthropic", self.anthropic),
            ("gemini", self.gemini),
            ("perplexity", self.perplexity),
            ("xai", self.xai),
            ("deepseek", self.deepseek),
            ("kimi", self.kimi),
        )
        return tuple(name for name, secret in providers if secret)

    def for_provider(self, provider: str) -> str:
        if provider not in {
            "openai",
            "anthropic",
            "gemini",
            "perplexity",
            "xai",
            "deepseek",
            "kimi",
        }:
            return ""
        return getattr(self, provider)


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
    morning_report_hour: int
    evening_report_hour: int
    weekly_report_weekday: int
    weekly_report_hour: int
    timezone: str
    github_token_expires_at: date | None
    approval_api_secret: str
    ai_provider_secrets: AIProviderSecrets


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
    morning_hour = int(os.environ.get("MORNING_REPORT_HOUR", "9"))
    report_hour = int(os.environ.get("EVENING_REPORT_HOUR", "21"))
    weekly_weekday = int(os.environ.get("WEEKLY_REPORT_WEEKDAY", "0"))
    weekly_hour = int(os.environ.get("WEEKLY_REPORT_HOUR", "9"))
    if monitor_interval < 60:
        raise RuntimeError("MONITOR_INTERVAL_SECONDS must be at least 60")
    if not 0 <= morning_hour <= 23:
        raise RuntimeError("MORNING_REPORT_HOUR must be between 0 and 23")
    if not 0 <= report_hour <= 23:
        raise RuntimeError("EVENING_REPORT_HOUR must be between 0 and 23")
    if not 0 <= weekly_weekday <= 6:
        raise RuntimeError("WEEKLY_REPORT_WEEKDAY must be between 0 and 6")
    if not 0 <= weekly_hour <= 23:
        raise RuntimeError("WEEKLY_REPORT_HOUR must be between 0 and 23")
    raw_expiry = os.environ.get("GITHUB_TOKEN_EXPIRES_AT", "").strip()
    try:
        github_token_expires_at = date.fromisoformat(raw_expiry) if raw_expiry else None
    except ValueError as exc:
        raise RuntimeError("GITHUB_TOKEN_EXPIRES_AT must use YYYY-MM-DD") from exc

    return Config(
        bot_token=bot_token,
        owner_ids=owner_ids,
        github_owner=os.environ.get("GITHUB_OWNER", "rashidd1987").strip(),
        github_token=os.environ.get("GITHUB_READ_TOKEN", "").strip(),
        request_timeout_seconds=float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10")),
        port=int(os.environ.get("PORT", "8080")),
        data_dir=os.environ.get("REPORT_BOT_DATA_DIR", "/data").strip() or "/data",
        monitor_interval_seconds=monitor_interval,
        morning_report_hour=morning_hour,
        evening_report_hour=report_hour,
        weekly_report_weekday=weekly_weekday,
        weekly_report_hour=weekly_hour,
        timezone=os.environ.get("REPORT_TIMEZONE", "Europe/Moscow").strip(),
        github_token_expires_at=github_token_expires_at,
        approval_api_secret=os.environ.get("APPROVAL_API_SECRET", "").strip(),
        ai_provider_secrets=AIProviderSecrets(
            openai=os.environ.get("OPENAI_API_KEY", "").strip(),
            anthropic=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            gemini=os.environ.get("GEMINI_API_KEY", "").strip(),
            perplexity=os.environ.get("PERPLEXITY_API_KEY", "").strip(),
            xai=os.environ.get("XAI_API_KEY", "").strip(),
            deepseek=os.environ.get("DEEPSEEK_API_KEY", "").strip(),
            kimi=os.environ.get("KIMI_API_KEY", "").strip(),
        ),
    )
