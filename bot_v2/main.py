#!/usr/bin/env python3
"""IQ BARAKAH — aiogram 3.x + asyncpg/PostgreSQL."""
import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot_v2.config import load_config
from bot_v2.db import setup_db, ensure_database, create_tables
from bot_v2.handlers import setup_routers
from bot_v2.middlewares import DbSessionMiddleware
from bot_v2.services.jarwas import setup_jarwas
from bot_v2.services.insights import setup_insights
from bot_v2.services.jobs import (
    job_jarwas_fajr,
    job_jarwas_friday,
    job_silence_check,
    job_progress_mirror,
)

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

    # ── Планировщик задач ──────────────────────────────────────
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Фаджр-напоминание: ежедневно 02:30 UTC = 05:30 МСК
    scheduler.add_job(
        job_jarwas_fajr, CronTrigger(hour=2, minute=30),
        args=[bot], id="fajr",
    )
    # Пятничная рефлексия: пятница 17:00 UTC = 20:00 МСК
    scheduler.add_job(
        job_jarwas_friday, CronTrigger(day_of_week="fri", hour=17, minute=0),
        args=[bot], id="friday",
    )
    # Silence check: ежедневно 07:00 UTC = 10:00 МСК
    scheduler.add_job(
        job_silence_check, CronTrigger(hour=7, minute=0),
        args=[bot, config.curator_ids], id="silence",
    )
    # Зеркало прогресса: воскресенье 16:00 UTC = 19:00 МСК
    scheduler.add_job(
        job_progress_mirror, CronTrigger(day_of_week="sun", hour=16, minute=0),
        args=[bot, config.miniapp_url], id="progress_mirror",
    )
    # Еженедельный урок: понедельник 06:00 UTC = 09:00 МСК
    scheduler.add_job(
        _job_weekly_lesson, CronTrigger(day_of_week="mon", hour=6, minute=0),
        args=[bot, config], id="weekly_lesson",
    )

    scheduler.start()
    logger.info("Scheduler started: fajr, friday, silence, progress_mirror, weekly_lesson(mon 06:00 UTC)")

    # ── Команды бота ──────────────────────────────────────────────
    await _setup_commands(bot, config)
    logger.info("Bot commands registered")

    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        scheduler.shutdown()


async def _job_weekly_lesson(bot: Bot, config):
    """Понедельник 06:00 UTC = 09:00 МСК — переключаем неделю и рассылаем урок.

    Каждый понедельник:
    - Неделя участника сдвигается вперёд (независимо от того, нажал ли он «Сдать»)
    - Отправляется урок новой недели
    - Если дошёл до последней недели — выпускается из программы

    «Сдать неделю» — только для рефлексии и уведомления куратора, не влияет на расписание.
    """
    from bot_v2.db.engine import get_session_factory
    from bot_v2.db.models import Participant, User
    from bot_v2.db.repositories.participant import ParticipantRepo
    from bot_v2.handlers.program import send_weekly_lesson
    from bot_v2.services.program import LEVEL_WEEKS
    from sqlalchemy import select

    async with get_session_factory()() as session:
        async with session.begin():
            result = await session.execute(
                select(Participant, User)
                .join(User, User.id == Participant.user_id)
                .where(Participant.is_active == True)
            )
            rows = result.all()
            count = 0
            for participant, _user in rows:
                try:
                    uid = participant.user_id
                    max_weeks = LEVEL_WEEKS.get(participant.level, 8)

                    if participant.week >= max_weeks:
                        repo = ParticipantRepo(session)
                        await repo.graduate(uid)
                        logger.info("Graduated %s (%s wk%s)", uid, participant.level, participant.week)
                        continue

                    # Переключаем на следующую неделю
                    participant.week += 1
                    await session.flush()

                    await send_weekly_lesson(bot, uid, participant, session, config)
                    count += 1
                except Exception as e:
                    logger.warning("weekly_lesson → %s: %s", participant.user_id, e)
    logger.info("Weekly lesson sent: %d чел.", count)


async def _setup_commands(bot: Bot, config) -> None:
    """Регистрирует команды в меню / Telegram."""

    # Команды для всех участников
    user_commands = [
        BotCommand(command="start",    description="🚀 Запустить / перезапустить бота"),
        BotCommand(command="progress", description="📊 Мой прогресс"),
        BotCommand(command="myid",     description="🪪 Мой Telegram ID"),
    ]

    # Полный список команд для каждого куратора
    curator_commands = user_commands + [
        BotCommand(command="participants", description="👥 Список участников"),
        BotCommand(command="activate",     description="✅ Активировать участника"),
        BotCommand(command="deactivate",   description="❌ Деактивировать участника"),
        BotCommand(command="reset",        description="♻️ Сбросить на неделю 1"),
        BotCommand(command="preview",      description="📺 Перейти на любую неделю"),
        BotCommand(command="tester",       description="🧪 Дать тестовый доступ"),
        BotCommand(command="send_now",     description="📤 Отправить урок прямо сейчас"),
        BotCommand(command="send_all",     description="📢 Разослать урок всем"),
        BotCommand(command="pair",         description="🤝 Создать пару участников"),
        BotCommand(command="analyze",      description="🔍 AI-анализ участника"),
        BotCommand(command="analytics",    description="📈 Общая аналитика"),
        BotCommand(command="myid",         description="🪪 Мой Telegram ID"),
        BotCommand(command="testjarwas",   description="🤖 Тест Jarwas API"),
        BotCommand(command="health",       description="🩺 Health check бота"),
        BotCommand(command="setcalllink",  description="🔗 Изменить ссылку на созвон"),
    ]

    # Глобальные команды (для всех)
    await bot.set_my_commands(user_commands)

    # Персональные команды для каждого куратора
    for curator_id in config.curator_ids:
        try:
            await bot.set_my_commands(
                curator_commands,
                scope=BotCommandScopeChat(chat_id=curator_id),
            )
        except Exception as e:
            logger.warning("Could not set curator commands for %s: %s", curator_id, e)


if __name__ == "__main__":
    asyncio.run(main())
