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

from aiohttp import web

from bot_v2.api.analyze import create_app as create_web_app
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
    job_check_payments,
    job_check_followups,
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

    # Загружаем дополнительных кураторов из БД
    from bot_v2.db.engine import get_session_factory
    from bot_v2.db.repositories import SettingsRepo
    async with get_session_factory()() as _s:
        _extra = await SettingsRepo(_s).get("extra_curators", "")
        if _extra:
            for _id in _extra.split(","):
                if _id and int(_id) not in config.curator_ids:
                    config.curator_ids.append(int(_id))
    logger.info("Curators: %s", config.curator_ids)

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

    # Проверка оплат ЮKassa: каждые 2 минуты
    scheduler.add_job(
        job_check_payments, "interval", minutes=2,
        args=[bot, config], id="check_payments",
    )

    scheduler.add_job(
        job_check_followups, "interval", minutes=30,
        args=[bot], id="check_followups",
    )

    scheduler.start()
    logger.info("Scheduler started: fajr, friday, silence, progress_mirror, weekly_lesson, check_payments, check_followups")

    # ── Команды бота ──────────────────────────────────────────────
    try:
        await _setup_commands(bot, config)
        logger.info("Bot commands registered")
    except Exception as e:
        logger.warning("Bot commands registration failed (non-critical): %s", e)

    logger.info("Starting bot + web server...")
    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 80)
    try:
        await site.start()
        logger.info("Web server started on port 80")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await runner.cleanup()
        scheduler.shutdown()


async def _job_weekly_lesson(bot: Bot, config):
    """Понедельник 06:00 UTC = 09:00 МСК — резервное авто-продвижение.

    Запускается только если участник НЕ завершил шаг сам (не нажал «Шаг выполнен»).
    Основная логика продвижения — по действию (нажатие кнопки + тест).
    Таймер — только страховка чтобы никто не завис.
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
                        logger.info("Graduated %s (%s step%s)", uid, participant.level, participant.week)
                        continue

                    # Проверяем: участник уже завершил шаг сам (week_ack есть)?
                    from bot_v2.db.models import WeekAck
                    from sqlalchemy import select as sa_select
                    ack_exists = await session.scalar(
                        sa_select(WeekAck.id).where(
                            WeekAck.user_id == uid,
                            WeekAck.level == participant.level,
                            WeekAck.week == participant.week,
                        )
                    )
                    if ack_exists:
                        # Уже завершил сам — таймер не вмешивается
                        continue

                    # Резервное авто-продвижение (шаг не завершён за неделю)
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
        BotCommand(command="reset",        description="♻️ Сбросить на шаг 1"),
        BotCommand(command="preview",      description="📺 Перейти на любой шаг"),
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
        BotCommand(command="gift",         description="🎁 Дать бесплатный доступ по user_id"),
        BotCommand(command="gift_code",    description="🔑 Создать одноразовую gift-ссылку"),
        BotCommand(command="gift_codes",   description="🔑 Создать N одноразовых ссылок"),
        BotCommand(command="gift_stats",   description="📊 Сколько мест использовано"),
        BotCommand(command="gift_reset",   description="♻️ Сбросить счётчик gift-ссылки"),
        BotCommand(command="forum_start",  description="🚀 Отправить диагностику форумщикам"),
        BotCommand(command="forum_ship",   description="🚢 Разослать Разбор корабля форумщикам"),
        BotCommand(command="forum_list",   description="🎟 Список участников форума"),
        BotCommand(command="forum_add",    description="➕ Добавить тест-билет форума"),
        BotCommand(command="forum_reset_counter", description="♻️ Сбросить нумерацию билетов"),
        BotCommand(command="user_info",    description="👤 Инфо об участнике по user_id"),
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
