import asyncio
import html
import logging
import ssl

import aiohttp
import certifi
from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from report_bot.config import Config, load_config
from report_bot.projects import PROJECTS, PROJECTS_BY_KEY
from report_bot.status import (
    StatusClient,
    all_sites_summary,
    format_datetime,
    project_summary,
    run_icon,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def is_owner(message: Message, config: Config) -> bool:
    return bool(message.from_user and message.from_user.id in config.owner_ids)


async def deny_untrusted(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    logger.warning("Rejected report bot request from Telegram user %s", user_id)


def build_router(config: Config, client: StatusClient) -> Router:
    router = Router(name="owner_reports")

    async def require_owner(message: Message) -> bool:
        if is_owner(message, config):
            return True
        await deny_untrusted(message)
        return False

    @router.message(Command("start", "help"))
    async def help_command(message: Message) -> None:
        if not await require_owner(message):
            return
        await message.answer(
            "<b>Mizan Project Reports</b>\n\n"
            "/projects — все проекты\n"
            "/iqbarakah — IQ Barakah\n"
            "/mizanlife — Mizan Life\n"
            "/mizanos — Mizan OS\n"
            "/status — доступность сайтов\n"
            "/releases — последние релизы\n"
            "/errors — последние ошибки\n"
            "/help — справка"
        )

    @router.message(Command("projects"))
    async def projects_command(message: Message) -> None:
        if not await require_owner(message):
            return
        summaries = await asyncio.gather(
            *(project_summary(client, project) for project in PROJECTS)
        )
        await message.answer("\n\n".join(summaries), disable_web_page_preview=True)

    for command, project in PROJECTS_BY_KEY.items():
        async def handler(
            message: Message,
            selected_project=project,
        ) -> None:
            if not await require_owner(message):
                return
            await message.answer(
                await project_summary(client, selected_project),
                disable_web_page_preview=True,
            )

        router.message.register(handler, Command(command))

    @router.message(Command("status"))
    async def status_command(message: Message) -> None:
        if not await require_owner(message):
            return
        await message.answer(await all_sites_summary(client))

    @router.message(Command("releases"))
    async def releases_command(message: Message) -> None:
        if not await require_owner(message):
            return
        lines = ["<b>Последние релизы и сборки</b>"]
        for project in PROJECTS:
            if not project.repo:
                continue
            runs = await client.workflow_runs(project.repo, limit=3)
            if runs is None:
                lines.append(f"\n⚠️ {project.title}: GitHub недоступен")
                continue
            lines.append(f"\n<b>{project.title}</b>")
            for run in runs:
                name = html.escape(run.get("name") or "Workflow")
                url = run.get("html_url") or project.health_url
                lines.append(
                    f'{run_icon(run.get("conclusion"), run.get("status"))} '
                    f'<a href="{url}">{name}</a> — '
                    f'{format_datetime(run.get("updated_at"))}'
                )
        await message.answer("\n".join(lines), disable_web_page_preview=True)

    @router.message(Command("errors"))
    async def errors_command(message: Message) -> None:
        if not await require_owner(message):
            return
        lines = ["<b>Последние ошибки автоматизаций</b>"]
        found = False
        for project in PROJECTS:
            if not project.repo:
                continue
            runs = await client.workflow_runs(project.repo, status="failure", limit=3)
            if runs is None:
                lines.append(f"\n⚠️ {project.title}: GitHub недоступен")
                continue
            for run in runs:
                found = True
                name = html.escape(run.get("name") or "Workflow")
                url = run.get("html_url") or project.health_url
                lines.append(
                    f'\n❌ {project.title}: <a href="{url}">{name}</a>\n'
                    f'{format_datetime(run.get("updated_at"))}'
                )
        if not found:
            lines.append("\n✅ Доступных ошибок не найдено")
        await message.answer("\n".join(lines), disable_web_page_preview=True)

    return router


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "mizan-project-reports"})


async def run_health_server(port: int) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/health", health)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logger.info("Health server listening on port %s", port)
    return runner


async def main() -> None:
    config = load_config()
    timeout = aiohttp.ClientTimeout(total=config.request_timeout_seconds)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        client = StatusClient(session, config.github_owner, config.github_token)
        bot = Bot(
            config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dispatcher = Dispatcher()
        dispatcher.include_router(build_router(config, client))
        health_runner = await run_health_server(config.port)

        try:
            logger.info("Starting owner-only project report bot")
            await dispatcher.start_polling(
                bot,
                allowed_updates=dispatcher.resolve_used_update_types(),
                handle_signals=True,
            )
        finally:
            await health_runner.cleanup()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
