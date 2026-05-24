#!/usr/bin/env python3
"""IQ BARAKAH — aiogram 3.x + asyncpg/PostgreSQL."""
import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot_v2.config import load_config
from bot_v2.db import setup_db, ensure_database, create_tables
from bot_v2.handlers import setup_routers
from bot_v2.middlewares import DbSessionMiddleware
from bot_v2.services.jarwas import setup_jarwas
from bot_v2.services.insights import setup_insights

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _mask_db_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        netloc = parts.netloc
        if "@" in netloc:
            credentials, host = netloc.rsplit("@", 1)
            user = credentials.split(":", 1)[0]
            netloc = f"{user}:***@{host}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return "<invalid database url>"


async def main():
    config = load_config()
    logger.info("Booting %s", config.version)
    logger.info("Database URL: %s", _mask_db_url(config.database_url))

    # DB
    await ensure_database(config.database_url)
    setup_db(config.database_url)
    await create_tables()
    logger.info("Database ready")

    # AI services
    setup_jarwas(config.anthropic_api_key)
    setup_insights(config.anthropic_api_key)

    # Bot & Dispatcher
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware — session injected into every handler
    dp.update.middleware(DbSessionMiddleware())

    # Config injected via workflow_data
    dp["config"] = config

    # Routers
    dp.include_router(setup_routers())

    # Weekly lesson job — воскресенье 09:00 UTC
    # (можно заменить на APScheduler или aiogram-scheduler)
    # Здесь показан шаблон; конкретный cron — в amvera.yml или отдельном процессе.

    logger.info("Starting bot...")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
