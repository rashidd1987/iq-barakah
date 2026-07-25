import asyncio
import hmac
import html
import json
import logging
import ssl

import aiohttp
import certifi
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from report_bot.approvals import Approval, ApprovalStore
from report_bot.config import Config, load_config
from report_bot.monitor import monitor_loop
from report_bot.projects import PROJECTS_BY_KEY, ProjectRegistry, validate_project
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

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📂 Проекты"), KeyboardButton(text="📡 Статус")],
        [KeyboardButton(text="🚀 Релизы"), KeyboardButton(text="❌ Ошибки")],
        [KeyboardButton(text="🧪 Подготовить PWA-релиз")],
        [KeyboardButton(text="➕ Добавить проект"), KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
)


class AddProject(StatesGroup):
    key = State()
    title = State()
    url = State()
    repo = State()


def approval_text(approval: Approval) -> str:
    status = {
        "pending": "⏳ Ожидает решения",
        "approved": "✅ Разрешено",
        "rejected": "⛔ Отклонено",
        "expired": "⌛️ Срок запроса истёк",
    }[approval.status]
    return (
        "🔐 <b>Требуется ваше разрешение</b>\n\n"
        f"<b>Проект:</b> {html.escape(approval.project)}\n"
        f"<b>Действие:</b> {html.escape(approval.action)}\n"
        f"<b>Что произойдёт:</b> {html.escape(approval.description)}\n"
        f"<b>Риск:</b> {html.escape(approval.risk)}\n\n"
        f"<b>Статус:</b> {status}\n"
        f"<code>{approval.id}</code>"
    )


def approval_keyboard(approval: Approval) -> InlineKeyboardMarkup | None:
    if approval.status != "pending":
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, разрешить",
                    callback_data=f"approval:approve:{approval.id}",
                ),
                InlineKeyboardButton(
                    text="⛔ Нет, отклонить",
                    callback_data=f"approval:reject:{approval.id}",
                ),
            ]
        ]
    )


def pwa_release_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧪 Запустить подготовку",
                    callback_data="release:pwa:start",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="release:pwa:cancel",
                ),
            ]
        ]
    )


def is_owner(message: Message, config: Config) -> bool:
    return bool(message.from_user and message.from_user.id in config.owner_ids)


async def deny_untrusted(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    logger.warning("Rejected report bot request from Telegram user %s", user_id)


def build_router(
    config: Config,
    client: StatusClient,
    registry: ProjectRegistry,
    approval_store: ApprovalStore,
) -> Router:
    router = Router(name="owner_reports")

    async def require_owner(message: Message) -> bool:
        if is_owner(message, config):
            return True
        await deny_untrusted(message)
        return False

    @router.message(Command("start", "help"))
    @router.message(lambda message: message.text == "ℹ️ Помощь")
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
            "/releasepwa — подготовить PWA-релиз\n"
            "/addproject — добавить проект\n"
            "/approvaltest — проверить запрос Да/Нет\n"
            "/cancel — отменить ввод\n"
            "/help — справка"
            "\n\nАвтоматически сообщаю только об изменениях и присылаю вечерний отчёт.",
            reply_markup=MENU,
        )

    @router.message(Command("projects"))
    @router.message(lambda message: message.text == "📂 Проекты")
    async def projects_command(message: Message) -> None:
        if not await require_owner(message):
            return
        summaries = await asyncio.gather(
            *(project_summary(client, project) for project in registry.all())
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
    @router.message(lambda message: message.text == "📡 Статус")
    async def status_command(message: Message) -> None:
        if not await require_owner(message):
            return
        await message.answer(await all_sites_summary(client, registry.all()))

    @router.message(Command("releases"))
    @router.message(lambda message: message.text == "🚀 Релизы")
    async def releases_command(message: Message) -> None:
        if not await require_owner(message):
            return
        lines = ["<b>Последние релизы и сборки</b>"]
        for project in registry.all():
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
    @router.message(lambda message: message.text == "❌ Ошибки")
    async def errors_command(message: Message) -> None:
        if not await require_owner(message):
            return
        lines = ["<b>Последние ошибки автоматизаций</b>"]
        found = False
        for project in registry.all():
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

    @router.message(Command("releasepwa"))
    @router.message(lambda message: message.text == "🧪 Подготовить PWA-релиз")
    async def prepare_pwa_release(message: Message) -> None:
        if not await require_owner(message):
            return
        await message.answer(
            "🧪 <b>Подготовить PWA-релиз IQ Barakah?</b>\n\n"
            "Облако выполнит TypeScript-проверку и соберёт PWA. "
            "После успешной сборки бот отдельно спросит разрешение "
            "на публикацию в production.\n\n"
            "На этом шаге сайт не изменяется.",
            reply_markup=pwa_release_keyboard(),
        )

    @router.callback_query(F.data.startswith("release:pwa:"))
    async def pwa_release_callback(callback: CallbackQuery) -> None:
        owner_id = callback.from_user.id
        if owner_id not in config.owner_ids:
            logger.warning("Rejected release callback from Telegram user %s", owner_id)
            await callback.answer("Нет доступа", show_alert=True)
            return
        action = (callback.data or "").rsplit(":", 1)[-1]
        if action == "cancel":
            await callback.answer("Отменено")
            if callback.message:
                await callback.message.edit_text(
                    "⚪️ Подготовка PWA-релиза отменена. Ничего не запускалось."
                )
            return
        if action != "start":
            await callback.answer("Некорректный запрос", show_alert=True)
            return

        await callback.answer("Проверяю очередь…")
        runs = await client.workflow_runs("iq-barakah", limit=10)
        if runs is None:
            result_text = (
                "❌ Не удалось проверить GitHub. Сборка не запущена. "
                "Попробуйте позже."
            )
        elif any(
            run.get("name") == "Release PWA"
            and run.get("status") in {"queued", "in_progress", "waiting", "pending"}
            for run in runs
        ):
            result_text = (
                "⏳ Подготовка PWA уже выполняется. Второй запуск не создан."
            )
        else:
            result = await client.dispatch_workflow(
                "iq-barakah",
                "release-pwa.yml",
                ref="main",
                inputs={
                    "target": "production",
                    "confirm_production": "RELEASE",
                },
            )
            result_text = {
                "started": (
                    "✅ Подготовка PWA-релиза запущена в облаке.\n\n"
                    "После тестов бот пришлёт отдельный запрос: "
                    "публиковать production или остановить релиз."
                ),
                "unauthorized": (
                    "🔒 GitHub не разрешил запуск workflow. "
                    "Сборка не запущена."
                ),
                "not_found": (
                    "❌ Workflow PWA не найден. Сборка не запущена."
                ),
                "failed": (
                    "❌ GitHub временно недоступен. Сборка не запущена."
                ),
            }[result]
        if callback.message:
            await callback.message.edit_text(result_text)

    @router.message(Command("cancel"))
    async def cancel_command(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        await state.clear()
        await message.answer("Добавление отменено.", reply_markup=MENU)

    @router.message(Command("addproject"))
    @router.message(lambda message: message.text == "➕ Добавить проект")
    async def add_project_command(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        await state.clear()
        await state.set_state(AddProject.key)
        await message.answer(
            "Введите короткий ключ проекта: 2–32 символа, например <code>myproject</code>.\n"
            "Для отмены: /cancel"
        )

    @router.message(AddProject.key)
    async def add_project_key(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        key = (message.text or "").strip().lower()
        try:
            validate_project(key, "Проект", "https://example.com", None)
            if registry.by_key(key):
                raise ValueError("Проект с таким ключом уже существует")
        except ValueError as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}\nПопробуйте ещё раз.")
            return
        await state.update_data(key=key)
        await state.set_state(AddProject.title)
        await message.answer("Введите название проекта.")

    @router.message(AddProject.title)
    async def add_project_title(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        title = (message.text or "").strip()
        if not 2 <= len(title) <= 80:
            await message.answer("⚠️ Название должно содержать от 2 до 80 символов.")
            return
        await state.update_data(title=title)
        await state.set_state(AddProject.url)
        await message.answer("Введите HTTPS-адрес проекта, например https://example.com/")

    @router.message(AddProject.url)
    async def add_project_url(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        data = await state.get_data()
        url = (message.text or "").strip()
        try:
            validate_project(data["key"], data["title"], url, None)
        except ValueError as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}\nПопробуйте ещё раз.")
            return
        await state.update_data(url=url)
        await state.set_state(AddProject.repo)
        await message.answer(
            "Введите имя GitHub-репозитория без ссылки или <code>-</code>, если его нет."
        )

    @router.message(AddProject.repo)
    async def add_project_repo(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        data = await state.get_data()
        repo_text = (message.text or "").strip()
        repo = None if repo_text == "-" else repo_text
        try:
            project = validate_project(
                data["key"], data["title"], data["url"], repo
            )
            registry.add(project)
        except ValueError as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}\nПопробуйте ещё раз.")
            return
        await state.clear()
        await message.answer(
            f"✅ Проект <b>{html.escape(project.title)}</b> добавлен и включён в мониторинг.",
            reply_markup=MENU,
        )

    @router.message(Command("approvaltest"))
    async def approval_test_command(message: Message) -> None:
        if not await require_owner(message):
            return
        approval, _ = approval_store.create(
            idempotency_key=f"manual-test:{message.chat.id}:{message.message_id}",
            project="Mizan Approval Center",
            action="Тест согласования",
            description="Проверить кнопки без запуска production-действий",
            risk="Безопасный тест: никаких внешних изменений",
            ttl_minutes=15,
        )
        await message.answer(
            approval_text(approval),
            reply_markup=approval_keyboard(approval),
        )

    @router.callback_query(F.data.startswith("approval:"))
    async def approval_callback(callback: CallbackQuery) -> None:
        owner_id = callback.from_user.id
        if owner_id not in config.owner_ids:
            logger.warning("Rejected approval callback from Telegram user %s", owner_id)
            await callback.answer("Нет доступа", show_alert=True)
            return
        parts = (callback.data or "").split(":", 2)
        if len(parts) != 3 or parts[1] not in {"approve", "reject"}:
            await callback.answer("Некорректный запрос", show_alert=True)
            return
        approval = approval_store.decide(
            parts[2],
            approved=parts[1] == "approve",
            owner_id=owner_id,
        )
        if approval is None:
            await callback.answer("Запрос не найден", show_alert=True)
            return
        callback_answers = {
            "approved": "Разрешено",
            "rejected": "Отклонено",
            "expired": "Срок запроса истёк",
            "pending": "Решение не сохранено",
        }
        await callback.answer(callback_answers[approval.status])
        if callback.message:
            await callback.message.edit_text(
                approval_text(approval),
                reply_markup=approval_keyboard(approval),
            )

    return router


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "mizan-project-reports"})


def approval_auth_ok(request: web.Request, secret: str) -> bool:
    if not secret:
        return False
    supplied = request.headers.get("Authorization", "")
    expected = f"Bearer {secret}"
    return hmac.compare_digest(
        supplied.encode("utf-8"),
        expected.encode("utf-8"),
    )


async def run_health_server(
    port: int,
    config: Config,
    bot: Bot,
    approval_store: ApprovalStore,
) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/health", health)

    async def create_approval(request: web.Request) -> web.Response:
        if not approval_auth_ok(request, config.approval_api_secret):
            raise web.HTTPUnauthorized()
        try:
            payload = await request.json()
            idempotency_key = str(payload["idempotency_key"]).strip()
            project = str(payload["project"]).strip()
            action = str(payload["action"]).strip()
            description = str(payload["description"]).strip()
            risk = str(payload["risk"]).strip()
            ttl_minutes = int(payload.get("ttl_minutes", 60))
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            aiohttp.ContentTypeError,
        ):
            raise web.HTTPBadRequest(text="invalid request") from None
        if (
            not 8 <= len(idempotency_key) <= 160
            or not 2 <= len(project) <= 80
            or not 2 <= len(action) <= 120
            or not 2 <= len(description) <= 500
            or not 2 <= len(risk) <= 300
            or not 5 <= ttl_minutes <= 1440
        ):
            raise web.HTTPBadRequest(text="invalid request")
        approval, created = approval_store.create(
            idempotency_key=idempotency_key,
            project=project,
            action=action,
            description=description,
            risk=risk,
            ttl_minutes=ttl_minutes,
        )
        if approval.status == "pending" and approval.notified_at is None:
            delivered = False
            for owner_id in config.owner_ids:
                try:
                    await bot.send_message(
                        owner_id,
                        approval_text(approval),
                        reply_markup=approval_keyboard(approval),
                    )
                    delivered = True
                except Exception:
                    logger.exception(
                        "Failed to deliver approval %s to owner %s",
                        approval.id,
                        owner_id,
                    )
            if not delivered:
                raise web.HTTPServiceUnavailable(text="notification unavailable")
            approval = approval_store.mark_notified(approval.id) or approval
        return web.json_response(
            {
                "id": approval.id,
                "status": approval.status,
                "expires_at": approval.expires_at,
            },
            status=201 if created else 200,
        )

    async def get_approval(request: web.Request) -> web.Response:
        if not approval_auth_ok(request, config.approval_api_secret):
            raise web.HTTPUnauthorized()
        approval = approval_store.get(request.match_info["approval_id"])
        if approval is None:
            raise web.HTTPNotFound()
        return web.json_response(
            {
                "id": approval.id,
                "status": approval.status,
                "expires_at": approval.expires_at,
                "decided_at": approval.decided_at,
            }
        )

    app.router.add_post("/approvals", create_approval)
    app.router.add_get("/approvals/{approval_id}", get_approval)
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
        registry = ProjectRegistry(config.data_dir)
        approval_store = ApprovalStore(config.data_dir)
        bot = Bot(
            config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dispatcher = Dispatcher()
        dispatcher.include_router(
            build_router(config, client, registry, approval_store)
        )
        health_runner = await run_health_server(
            config.port, config, bot, approval_store
        )
        monitor_task = asyncio.create_task(
            monitor_loop(
                bot,
                config.owner_ids,
                client,
                registry,
                config.data_dir,
                config.monitor_interval_seconds,
                config.evening_report_hour,
                config.timezone,
                config.github_token_expires_at,
            )
        )

        try:
            logger.info("Starting owner-only project report bot")
            await dispatcher.start_polling(
                bot,
                allowed_updates=dispatcher.resolve_used_update_types(),
                handle_signals=True,
            )
        finally:
            monitor_task.cancel()
            await asyncio.gather(monitor_task, return_exceptions=True)
            await health_runner.cleanup()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
