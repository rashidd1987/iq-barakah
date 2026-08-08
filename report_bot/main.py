import asyncio
from io import BytesIO
from datetime import date, datetime
import hmac
import html
import json
import logging
import ssl
from zoneinfo import ZoneInfo

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
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    BufferedInputFile,
)

from report_bot.ai_gateway import (
    AI_PROVIDERS_BY_KEY,
    ask_ai,
    choose_auto_provider,
    choose_judge,
    provider_titles,
    synthesis_task,
)
from report_bot.approvals import Approval, ApprovalStore
from report_bot.config import Config, load_config
from report_bot.council import (
    CouncilContext,
    council_views,
    executive_recommendation,
    select_project,
)
from report_bot.day_plan import DayPlanStore, build_day_plan
from report_bot.ideas import IdeaStore
from report_bot.knowledge import ProjectKnowledgeLibrary
from report_bot.monitor import (
    ProjectState,
    capture_state,
    monitor_loop,
    morning_brief,
    weekly_task_report,
)
from report_bot.projects import PROJECTS_BY_KEY, ProjectRegistry, validate_project
from report_bot.status import (
    StatusClient,
    all_sites_summary,
    format_datetime,
    project_summary,
    run_icon,
)
from report_bot.tasks import (
    OwnerTask,
    TaskStore,
    format_user_date,
    parse_task_details,
    parse_user_date,
)
from report_bot.voice import extract_voice_task, transcribe_voice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BOT_COMMANDS = (
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="projects", description="Все проекты"),
    BotCommand(command="iqbarakah", description="Статус IQ Barakah"),
    BotCommand(command="mizanlife", description="Статус Mizan Life"),
    BotCommand(command="mizanos", description="Статус Mizan OS"),
    BotCommand(command="status", description="Состояние автоматизаций"),
    BotCommand(command="council", description="Совет ролей по задаче"),
    BotCommand(command="library", description="Библиотека проектов"),
    BotCommand(command="use", description="Выбрать активный проект"),
    BotCommand(command="brief", description="Обновить паспорт проекта"),
    BotCommand(command="tasks", description="Открытые поручения"),
    BotCommand(command="today", description="Поручения на сегодня"),
    BotCommand(command="morning", description="Утренний бриф"),
    BotCommand(command="plan", description="Предложить план дня"),
    BotCommand(command="evening", description="Подвести итоги дня"),
    BotCommand(command="weekly", description="Недельный отчёт"),
    BotCommand(command="automation", description="Облачная автоматизация"),
    BotCommand(command="newtask", description="Создать мою задачу"),
    BotCommand(command="agenttask", description="Поручить задачу агенту"),
    BotCommand(command="agenttasks", description="Задачи агента"),
    BotCommand(command="newidea", description="Сохранить идею"),
    BotCommand(command="ideas", description="База идей"),
    BotCommand(command="ideasexport", description="Экспорт идей для ИИ"),
    BotCommand(command="done", description="Завершить поручение"),
    BotCommand(command="releases", description="Последние релизы"),
    BotCommand(command="errors", description="Последние ошибки"),
    BotCommand(command="releasepwa", description="Подготовить PWA-релиз"),
    BotCommand(command="help", description="Справка по командам"),
)

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Старт")],
        [KeyboardButton(text="🧠 Совет ИИ")],
        [KeyboardButton(text="📚 Библиотека проектов")],
        [KeyboardButton(text="👤 Мои задачи"), KeyboardButton(text="➕ Моя задача")],
        [KeyboardButton(text="🤖 Поручить агенту"), KeyboardButton(text="📋 Задачи агента")],
        [KeyboardButton(text="💡 Новая идея"), KeyboardButton(text="📒 База идей")],
        [KeyboardButton(text="☀️ Утренний бриф"), KeyboardButton(text="🎯 План дня")],
        [KeyboardButton(text="🌙 Итоги дня"), KeyboardButton(text="📊 Неделя")],
        [KeyboardButton(text="☁️ Автоматизация")],
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
    brief = State()


class OwnerCouncil(StatesGroup):
    task = State()


class SubscriptionCouncil(StatesGroup):
    task = State()


class ApiCouncil(StatesGroup):
    task = State()


class TaskCreation(StatesGroup):
    details = State()


class AgentTaskCreation(StatesGroup):
    details = State()


class IdeaCreation(StatesGroup):
    text = State()


class TaskReview(StatesGroup):
    completion_evidence = State()
    postpone_date = State()
    postpone_reason = State()
    cancel_reason = State()


def council_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆓 Без расходов",
                    callback_data="councilmode:builtin",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚡ Автономно через API",
                    callback_data="councilmode:api",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Использовать подписку",
                    callback_data="councilmode:subscriptions",
                )
            ],
        ]
    )


def api_provider_keyboard(configured: tuple[str, ...]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="⭐ Автовыбор",
                callback_data="aipick:auto",
            )
        ],
        [
            InlineKeyboardButton(
                text="👥 Выбрать несколько",
                callback_data="aipick:multi",
            ),
            InlineKeyboardButton(
                text="🏛 Полный совет",
                callback_data="aipick:all",
            ),
        ],
    ]
    rows.extend(
        [
            InlineKeyboardButton(
                text=AI_PROVIDERS_BY_KEY[key].title,
                callback_data=f"aipick:{key}",
            )
        ]
        for key in configured
        if key in AI_PROVIDERS_BY_KEY
    )
    rows.append(
        [InlineKeyboardButton(text="Отмена", callback_data="aipick:cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def multi_provider_keyboard(
    configured: tuple[str, ...],
    selected: tuple[str, ...],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"{'✅' if key in selected else '◻️'} "
                    f"{AI_PROVIDERS_BY_KEY[key].title}"
                ),
                callback_data=f"aimulti:toggle:{key}",
            )
        ]
        for key in configured
        if key in AI_PROVIDERS_BY_KEY
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=f"Продолжить ({len(selected)})",
                callback_data="aimulti:done",
            ),
            InlineKeyboardButton(text="Отмена", callback_data="aimulti:cancel"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_links_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Открыть ChatGPT", url="https://chatgpt.com/"),
                InlineKeyboardButton(text="Открыть Claude", url="https://claude.ai/new"),
            ],
            [
                InlineKeyboardButton(
                    text="Открыть Gemini", url="https://gemini.google.com/app"
                )
            ],
        ]
    )


def approval_text(approval: Approval) -> str:
    status = {
        "pending": "⏳ Ожидает решения",
        "approved": "✅ Разрешено",
        "rejected": "⛔ Отклонено",
        "expired": "⌛️ Срок запроса истёк",
    }[approval.status]
    source = {
        "telegram": " через Telegram",
        "github": " через GitHub",
        None: "",
    }[approval.decision_source]
    return (
        "🔐 <b>Требуется ваше разрешение</b>\n\n"
        f"<b>Проект:</b> {html.escape(approval.project)}\n"
        f"<b>Действие:</b> {html.escape(approval.action)}\n"
        f"<b>Что произойдёт:</b> {html.escape(approval.description)}\n"
        f"<b>Риск:</b> {html.escape(approval.risk)}\n\n"
        f"<b>Статус:</b> {status}{source}\n"
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


def automation_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤖 Android preview",
                    callback_data="auto:pick:android:preview",
                ),
                InlineKeyboardButton(
                    text="🍎 iOS preview",
                    callback_data="auto:pick:ios:preview",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Android production",
                    callback_data="auto:pick:android:production",
                ),
                InlineKeyboardButton(
                    text="🚀 iOS production",
                    callback_data="auto:pick:ios:production",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧪 PWA-релиз",
                    callback_data="auto:pwa",
                )
            ],
        ]
    )


def automation_confirmation_keyboard(
    platform: str, profile: str
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Запустить",
                    callback_data=f"auto:run:{platform}:{profile}",
                ),
                InlineKeyboardButton(text="Отмена", callback_data="auto:cancel"),
            ]
        ]
    )


def task_keyboard(task: OwnerTask) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выполнено",
                    callback_data=f"task:done:{task.id}",
                )
            ]
        ]
    )


def agent_task_keyboard(task: OwnerTask) -> InlineKeyboardMarkup:
    if task.agent_status == "queued":
        return InlineKeyboardMarkup(inline_keyboard=[])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Передать Codex",
                    callback_data=f"agent:pick:{task.id}",
                )
            ]
        ]
    )


def agent_confirmation_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Создать PR",
                    callback_data=f"agent:run:{task_id}",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"agent:cancel:{task_id}",
                ),
            ]
        ]
    )


def voice_intent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💡 Сохранить идею", callback_data="voice:idea")],
            [
                InlineKeyboardButton(text="👤 Моя задача", callback_data="voice:manual"),
                InlineKeyboardButton(text="🤖 Задача Codex", callback_data="voice:agent"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="voice:cancel")],
        ]
    )


def voice_task_confirmation_keyboard(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Создать",
                    callback_data=f"voicecreate:{kind}",
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data="voicecreate:cancel"),
            ]
        ]
    )


def plan_suggestion_keyboard(suggestion_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить в поручения",
                    callback_data=f"dayplan:add:{suggestion_id}",
                )
            ]
        ]
    )


async def send_automatic_day_plan(
    bot: Bot,
    owner_ids: frozenset[int],
    states: dict[str, ProjectState],
    registry: ProjectRegistry,
    task_store: TaskStore,
    day_plan_store: DayPlanStore,
    active_project: str,
    today: date,
) -> None:
    """Send persisted suggestions; creating a task still requires owner action."""
    suggestions = day_plan_store.replace(
        today,
        build_day_plan(
            states,
            registry,
            task_store,
            today,
            active_project,
        ),
    )
    heading = (
        "🎯 <b>Предложения на сегодня</b>\n\n"
        "Выберите только нужные действия. Без нажатия ничего не создаётся "
        "и не запускается."
    )
    for owner_id in owner_ids:
        await bot.send_message(owner_id, heading)
        for index, suggestion in enumerate(suggestions, 1):
            project = registry.by_key(suggestion.project_key)
            title = project.title if project else suggestion.project_key
            text = (
                f"<b>{index}. {html.escape(suggestion.title)}</b>\n"
                f"Проект: {html.escape(title)}\n"
                f"Почему: {html.escape(suggestion.reason)}\n"
                f"Готово, когда: {html.escape(suggestion.success_criterion)}"
            )
            await bot.send_message(
                owner_id,
                text,
                reply_markup=(
                    None
                    if suggestion.accepted_task_id
                    else plan_suggestion_keyboard(suggestion.id)
                ),
            )


def task_review_keyboard(task: OwnerTask) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выполнено",
                    callback_data=f"review:done:{task.id}",
                ),
                InlineKeyboardButton(
                    text="➡️ Перенести",
                    callback_data=f"review:postpone:{task.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⛔ Отменить",
                    callback_data=f"review:cancel:{task.id}",
                )
            ],
        ]
    )


def extract_task_evidence(message: Message) -> str:
    text = (message.text or "").strip()
    if text:
        return text
    caption = (message.caption or "").strip()
    has_photo = bool(message.photo)
    document = message.document
    has_image_document = bool(
        document and (document.mime_type or "").startswith("image/")
    )
    if has_photo or has_image_document:
        reference = f"Скриншот Telegram, сообщение #{message.message_id}"
        return f"{reference}: {caption}" if caption else reference
    return ""


def task_text(task: OwnerTask, project_title: str) -> str:
    owner = "Codex (только PR)" if task.kind == "agent" else task.responsible
    status = ""
    if task.kind == "agent":
        status = (
            "\nСтатус агента: "
            + ("⏳ запущен" if task.agent_status == "queued" else "⚪️ ожидает запуска")
        )
    return (
        f"📌 <b>{html.escape(task.title)}</b>\n"
        f"Проект: {html.escape(project_title)}\n"
        f"Срок: <code>{format_user_date(task.due_date)}</code>\n"
        f"Ответственный: {html.escape(owner)}{status}\n"
        f"Готово, когда: {html.escape(task.success_criterion)}\n"
        f"ID: <code>{task.id}</code>"
    )


def council_keyboard(project_key: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🔎 Проверить глубже",
                callback_data=f"council:inspect:{project_key}",
            )
        ]
    ]
    if project_key == "iqbarakah":
        rows.append(
            [
                InlineKeyboardButton(
                    text="🧪 Рассмотреть PWA-релиз",
                    callback_data="council:pwa:iqbarakah",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Отмена",
                callback_data=f"council:cancel:{project_key}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def is_owner(message: Message, config: Config) -> bool:
    return bool(message.from_user and message.from_user.id in config.owner_ids)


async def refresh_approval_messages(bot: Bot, approval: Approval) -> None:
    for chat_id, message_id in approval.telegram_messages:
        try:
            await bot.edit_message_text(
                approval_text(approval),
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=approval_keyboard(approval),
            )
        except Exception:
            logger.warning(
                "Could not refresh approval message %s/%s",
                chat_id,
                message_id,
                exc_info=True,
            )


async def approval_reconciliation_loop(
    bot: Bot,
    client: StatusClient,
    store: ApprovalStore,
) -> None:
    while True:
        try:
            for approval in store.pending():
                if not approval.github_repository or not approval.github_run_id:
                    continue
                run = await client.workflow_run(
                    approval.github_repository,
                    approval.github_run_id,
                )
                if not run:
                    continue
                status = run.get("status")
                conclusion = run.get("conclusion")
                approved: bool | None = None
                if status == "completed":
                    approved = conclusion == "success"
                if approved is None:
                    continue
                decided = store.decide(
                    approval.id,
                    approved=approved,
                    owner_id=None,
                    source="github",
                )
                if decided:
                    await refresh_approval_messages(bot, decided)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Approval reconciliation iteration failed")
        await asyncio.sleep(15)
async def deny_untrusted(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    logger.warning("Rejected report bot request from Telegram user %s", user_id)


def build_router(
    config: Config,
    session: aiohttp.ClientSession,
    client: StatusClient,
    registry: ProjectRegistry,
    knowledge: ProjectKnowledgeLibrary,
    approval_store: ApprovalStore,
    task_store: TaskStore,
    day_plan_store: DayPlanStore,
    idea_store: IdeaStore,
) -> Router:
    router = Router(name="owner_reports")

    async def require_owner(message: Message) -> bool:
        if is_owner(message, config):
            return True
        await deny_untrusted(message)
        return False

    @router.message(Command("start", "help"))
    @router.message(lambda message: message.text == "🏠 Старт")
    @router.message(lambda message: message.text == "ℹ️ Помощь")
    async def help_command(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        await state.clear()
        await message.answer(
            "<b>Mizan Project Reports</b>\n\n"
            "/projects — все проекты\n"
            "/iqbarakah — IQ Barakah\n"
            "/mizanlife — Mizan Life\n"
            "/mizanos — Mizan OS\n"
            "/status — доступность сайтов\n"
            "/council — бесплатный, API или подписной совет\n"
            "/library — паспорта и активный проект\n"
            "/use ключ — выбрать проект для коротких задач\n"
            "/brief текст — обновить паспорт активного проекта\n"
            "/tasks — мои открытые задачи\n"
            "/today — мои задачи на сегодня и просроченные\n"
            "/morning — утренний бриф по всем проектам\n"
            "/plan — предложить до трёх действий на сегодня\n"
            "/evening — подвести итоги по срочным поручениям\n"
            "/weekly — отчёт по поручениям за 7 дней\n"
            "/automation — облачные сборки с телефона\n"
            "/newtask — моя задача; бот будет напоминать\n"
            "/agenttask — Codex готовит изменения в отдельном PR\n"
            "/agenttasks — открытые задачи Codex\n"
            "/newidea — сохранить идею\n"
            "/ideas — последние идеи\n"
            "/ideasexport — файлы для любой ИИ\n"
            "/done ID — отметить поручение выполненным\n"
            "/releases — последние релизы\n"
            "/errors — последние ошибки\n"
            "/releasepwa — подготовить PWA-релиз\n"
            "/addproject — добавить проект\n"
            "/approvaltest — проверить запрос Да/Нет\n"
            "/cancel — отменить ввод\n"
            "/help — справка"
            "\n\nМои задачи выполняете вы; бот напоминает. "
            "Задачи агенту выполняет Codex и создаёт PR; "
            "main и production не изменяются.",
            reply_markup=MENU,
        )

    async def save_idea(message: Message, text: str, source: str) -> bool:
        try:
            owner_id = message.from_user.id if message.from_user else 0
            idea = idea_store.create(
                text=text,
                project_key=knowledge.active_project,
                source=source,
                created_by=owner_id,
            )
        except (ValueError, OSError) as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}")
            return False
        await message.answer(
            "💡 <b>Идея сохранена постоянно</b>\n\n"
            f"Проект: {html.escape(idea.project_key)}\n"
            f"{html.escape(idea.text)}\n\nID: <code>{idea.id}</code>",
            reply_markup=MENU,
        )
        return True

    @router.message(Command("newidea"))
    @router.message(lambda message: message.text == "💡 Новая идея")
    async def new_idea_command(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        raw = (message.text or "").split(maxsplit=1)
        if len(raw) == 2 and raw[0].startswith("/newidea"):
            await save_idea(message, raw[1], "text")
            return
        await state.set_state(IdeaCreation.text)
        await message.answer(
            "💡 <b>Новая идея</b>\n\n"
            "Отправьте текст или голосовое сообщение.\n"
            "Для отмены: /cancel"
        )

    @router.message(IdeaCreation.text, F.text)
    async def idea_text_received(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            await state.clear()
            return
        if (message.text or "").strip() == "/cancel":
            await state.clear()
            await message.answer("Ввод идеи отменён.", reply_markup=MENU)
            return
        if await save_idea(message, message.text or "", "text"):
            await state.clear()

    @router.message(Command("ideas"))
    @router.message(lambda message: message.text == "📒 База идей")
    async def ideas_command(message: Message) -> None:
        if not await require_owner(message):
            return
        ideas = idea_store.all()
        if not ideas:
            await message.answer("📒 База идей пока пуста.", reply_markup=MENU)
            return
        await message.answer(f"📒 <b>База идей</b>\n\nВсего: {len(ideas)}")
        for idea in ideas[:20]:
            created = datetime.fromisoformat(idea.created_at).strftime("%d.%m.%Y")
            await message.answer(
                f"💡 <b>{created} · {html.escape(idea.project_key)}</b>\n"
                f"{html.escape(idea.text)}\nID: <code>{idea.id}</code>"
            )
        if len(ideas) > 20:
            await message.answer(f"Показаны 20 из {len(ideas)}. Все: /ideasexport")

    @router.message(Command("ideasexport"))
    async def ideas_export_command(message: Message) -> None:
        if not await require_owner(message):
            return
        if not idea_store.all():
            await message.answer("📒 База идей пока пуста.")
            return
        stamp = datetime.now(ZoneInfo(config.timezone)).strftime("%Y-%m-%d")
        await message.answer_document(
            BufferedInputFile(
                idea_store.export_markdown().encode("utf-8"),
                filename=f"mizan-ideas-{stamp}.md",
            ),
            caption="🧠 Markdown: загрузите этот файл в любую ИИ.",
        )
        await message.answer_document(
            BufferedInputFile(
                idea_store.export_json().encode("utf-8"),
                filename=f"mizan-ideas-{stamp}.json",
            ),
            caption="🛠 JSON: для автоматизаций и переноса.",
        )

    @router.message(F.voice)
    async def voice_received(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            await state.clear()
            return
        voice = message.voice
        if voice is None:
            return
        if voice.file_size and voice.file_size > 20 * 1024 * 1024:
            await message.answer("⚠️ Голосовое сообщение больше 20 МБ.")
            return
        await message.answer("🎙 Распознаю голос…")
        try:
            destination = BytesIO()
            downloaded = await message.bot.download(voice, destination=destination)
            if downloaded is None:
                raise RuntimeError("Не удалось скачать голосовое сообщение")
            transcript = await transcribe_voice(
                session,
                config.ai_provider_secrets.openai,
                destination.getvalue(),
            )
        except (ValueError, RuntimeError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("Voice transcription failed: %s", type(exc).__name__)
            await message.answer(f"⚠️ {html.escape(str(exc))}", reply_markup=MENU)
            return
        await state.clear()
        await state.update_data(
            voice_transcript=transcript,
            voice_project_key=knowledge.active_project,
        )
        await message.answer(
            "🎙 <b>Текст голосового</b>\n\n"
            f"{html.escape(transcript)}\n\n"
            "Что сделать с этой записью?",
            reply_markup=voice_intent_keyboard(),
        )

    @router.callback_query(F.data.startswith("voice:"))
    async def voice_intent_callback(
        callback: CallbackQuery,
        state: FSMContext,
    ) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        action = (callback.data or "").split(":", 1)[-1]
        if action not in {"idea", "manual", "agent", "cancel"}:
            await callback.answer("Неизвестное действие", show_alert=True)
            return
        data = await state.get_data()
        transcript = str(data.get("voice_transcript", "")).strip()
        project_key = str(data.get("voice_project_key", knowledge.active_project))
        if not transcript:
            await callback.answer("Черновик уже истёк", show_alert=True)
            return
        if action == "cancel":
            await state.clear()
            await callback.answer("Отменено")
            if callback.message:
                await callback.message.edit_text("❌ Голосовая запись не сохранена.")
            return
        if action == "idea":
            try:
                idea = idea_store.create(
                    text=transcript,
                    project_key=project_key,
                    source="voice",
                    created_by=callback.from_user.id,
                )
            except (ValueError, OSError) as exc:
                await callback.answer(str(exc), show_alert=True)
                return
            await state.clear()
            await callback.answer("Идея сохранена")
            if callback.message:
                await callback.message.edit_text(
                    "💡 <b>Идея сохранена постоянно</b>\n\n"
                    f"{html.escape(idea.text)}\nID: <code>{idea.id}</code>"
                )
            return
        if action == "agent":
            project = registry.by_key(project_key)
            if project is None or not project.repo:
                await callback.answer(
                    "У проекта нет GitHub-репозитория",
                    show_alert=True,
                )
                return
        await callback.answer("Готовлю черновик…")
        try:
            draft = await extract_voice_task(
                session,
                config.ai_provider_secrets.openai,
                transcript,
                today=datetime.now(ZoneInfo(config.timezone)).date(),
            )
        except (ValueError, RuntimeError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("Voice task extraction failed: %s", type(exc).__name__)
            if callback.message:
                await callback.message.answer(f"⚠️ {html.escape(str(exc))}")
            return
        await state.update_data(
            voice_task_kind=action,
            voice_task_title=draft.title,
            voice_task_due=draft.due_date.isoformat(),
            voice_task_criterion=draft.success_criterion,
        )
        responsible = "Codex" if action == "agent" else "Вы"
        if callback.message:
            await callback.message.edit_text(
                "📋 <b>Проверьте черновик</b>\n\n"
                f"Задача: {html.escape(draft.title)}\n"
                f"Срок: <code>{format_user_date(draft.due_date)}</code>\n"
                f"Готово, когда: {html.escape(draft.success_criterion)}\n"
                f"Исполнитель: {responsible}\n\n"
                "Без нажатия задача не создастся.",
                reply_markup=voice_task_confirmation_keyboard(action),
            )

    @router.callback_query(F.data.startswith("voicecreate:"))
    async def voice_task_create_callback(
        callback: CallbackQuery,
        state: FSMContext,
    ) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        kind = (callback.data or "").split(":", 1)[-1]
        if kind == "cancel":
            await state.clear()
            await callback.answer("Отменено")
            if callback.message:
                await callback.message.edit_text("❌ Задача не создана.")
            return
        if kind not in {"manual", "agent"}:
            await callback.answer("Неизвестный тип", show_alert=True)
            return
        data = await state.get_data()
        if data.get("voice_task_kind") != kind:
            await callback.answer("Черновик уже истёк", show_alert=True)
            return
        project_key = str(data.get("voice_project_key", ""))
        project = registry.by_key(project_key)
        if project is None or (kind == "agent" and not project.repo):
            await callback.answer("Проект больше недоступен", show_alert=True)
            return
        try:
            task = task_store.create(
                project_key=project.key,
                title=str(data["voice_task_title"]),
                due_date=date.fromisoformat(str(data["voice_task_due"])),
                success_criterion=str(data["voice_task_criterion"]),
                created_by=callback.from_user.id,
                responsible="Codex" if kind == "agent" else "Владелец",
                kind=kind,
            )
        except (KeyError, ValueError, OSError) as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.clear()
        await callback.answer("Задача создана")
        if callback.message:
            await callback.message.edit_text(
                ("🤖" if kind == "agent" else "👤")
                + " <b>Задача создана из голоса</b>\n\n"
                + task_text(task, project.title),
                reply_markup=(
                    agent_task_keyboard(task) if kind == "agent" else task_keyboard(task)
                ),
            )

    async def send_tasks(
        message: Message,
        tasks: tuple[OwnerTask, ...],
        *,
        heading: str,
    ) -> None:
        if not tasks:
            await message.answer(f"{heading}\n\n✅ Задач нет.")
            return
        await message.answer(f"{heading}\n\nНайдено: {len(tasks)}")
        for task in tasks[:20]:
            project = registry.by_key(task.project_key)
            title = project.title if project else task.project_key
            await message.answer(
                task_text(task, title),
                reply_markup=(
                    agent_task_keyboard(task) if task.kind == "agent" else task_keyboard(task)
                ),
            )
        if len(tasks) > 20:
            await message.answer(
                f"Показаны первые 20 из {len(tasks)} поручений."
            )

    @router.message(Command("tasks"))
    @router.message(lambda message: message.text == "👤 Мои задачи")
    @router.message(lambda message: message.text == "✅ Поручения")
    async def tasks_command(message: Message) -> None:
        if not await require_owner(message):
            return
        await send_tasks(
            message,
            task_store.open_manual(),
            heading="👤 <b>Мои открытые задачи</b>",
        )

    @router.message(Command("today"))
    async def today_command(message: Message) -> None:
        if not await require_owner(message):
            return
        await send_tasks(
            message,
            task_store.due(datetime.now(ZoneInfo(config.timezone)).date()),
            heading="📅 <b>На сегодня и просроченные</b>",
        )

    @router.message(Command("agenttasks"))
    @router.message(lambda message: message.text == "📋 Задачи агента")
    async def agent_tasks_command(message: Message) -> None:
        if not await require_owner(message):
            return
        await send_tasks(
            message,
            task_store.open_agent(),
            heading="🤖 <b>Открытые задачи Codex</b>",
        )

    @router.message(Command("morning"))
    @router.message(lambda message: message.text == "☀️ Утренний бриф")
    async def morning_command(message: Message) -> None:
        if not await require_owner(message):
            return
        states = await capture_state(client, registry)
        today = datetime.now(ZoneInfo(config.timezone)).date()
        await message.answer(
            morning_brief(states, registry, task_store, approval_store, today)
        )

    @router.message(Command("plan"))
    @router.message(lambda message: message.text == "🎯 План дня")
    async def day_plan_command(message: Message) -> None:
        if not await require_owner(message):
            return
        today = datetime.now(ZoneInfo(config.timezone)).date()
        states = await capture_state(client, registry)
        try:
            suggestions = day_plan_store.replace(
                today,
                build_day_plan(
                    states,
                    registry,
                    task_store,
                    today,
                    knowledge.active_project,
                ),
            )
        except OSError:
            logger.exception("Could not persist owner day plan")
            await message.answer("⚠️ Не удалось сохранить план дня. Повторите позже.")
            return
        pending_count = len(approval_store.pending())
        overdue_count = len(
            [
                task
                for task in task_store.open_manual()
                if task.due_date < today.isoformat()
            ]
        )
        await message.answer(
            "🎯 <b>План дня</b>\n\n"
            f"Предложений: <b>{len(suggestions)}</b>\n"
            f"Просроченных поручений: <b>{overdue_count}</b>\n"
            f"Решений ожидают: <b>{pending_count}</b>\n\n"
            "Нажмите только те действия, которые хотите добавить. "
            "Без нажатия ничего не запускается."
        )
        for index, suggestion in enumerate(suggestions, 1):
            project = registry.by_key(suggestion.project_key)
            project_title = project.title if project else suggestion.project_key
            accepted = suggestion.accepted_task_id is not None
            await message.answer(
                f"<b>{index}. {html.escape(suggestion.title)}</b>\n"
                f"Проект: {html.escape(project_title)}\n"
                f"Почему: {html.escape(suggestion.reason)}\n"
                f"Готово, когда: {html.escape(suggestion.success_criterion)}"
                + ("\n\n✅ Уже добавлено в поручения" if accepted else ""),
                reply_markup=(
                    None
                    if accepted
                    else plan_suggestion_keyboard(suggestion.id)
                ),
            )

    @router.callback_query(F.data.startswith("dayplan:"))
    async def day_plan_callback(callback: CallbackQuery) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        parts = (callback.data or "").split(":", 2)
        if len(parts) != 3 or parts[1] != "add":
            await callback.answer("Некорректное действие", show_alert=True)
            return
        suggestion = day_plan_store.get(parts[2])
        if suggestion is None:
            await callback.answer(
                "План устарел. Сформируйте новый: /plan", show_alert=True
            )
            return
        if suggestion.accepted_task_id:
            await callback.answer("Уже добавлено")
            if callback.message:
                await callback.message.edit_reply_markup(reply_markup=None)
            return
        task = task_store.find_open(suggestion.project_key, suggestion.title)
        try:
            if task is None:
                task = task_store.create(
                    project_key=suggestion.project_key,
                    title=suggestion.title,
                    due_date=datetime.now(ZoneInfo(config.timezone)).date(),
                    success_criterion=suggestion.success_criterion,
                    created_by=callback.from_user.id,
                )
            day_plan_store.mark_accepted(suggestion.id, task.id)
        except OSError:
            logger.exception("Could not persist accepted day-plan suggestion")
            await callback.answer("Не удалось сохранить поручение", show_alert=True)
            return
        await callback.answer("Добавлено в поручения")
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
            project = registry.by_key(task.project_key)
            await callback.message.answer(
                "✅ <b>Добавлено в поручения</b>\n\n"
                + task_text(task, project.title if project else task.project_key),
                reply_markup=task_keyboard(task),
            )

    async def send_evening_review(message: Message) -> None:
        today = datetime.now(ZoneInfo(config.timezone)).date()
        tasks = task_store.due(today)
        if not tasks:
            await message.answer(
                "🌙 <b>Итоги дня</b>\n\n✅ Срочных открытых поручений нет."
            )
            return
        await message.answer(
            "🌙 <b>Итоги дня</b>\n\n"
            f"Нужно разобрать поручений: <b>{len(tasks)}</b>.\n"
            "Для каждого выберите результат. Без выбора данные не изменятся."
        )
        for task in tasks[:20]:
            project = registry.by_key(task.project_key)
            await message.answer(
                task_text(task, project.title if project else task.project_key),
                reply_markup=task_review_keyboard(task),
            )

    @router.message(Command("evening"))
    @router.message(lambda message: message.text == "🌙 Итоги дня")
    async def evening_review_command(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        await state.clear()
        await send_evening_review(message)

    @router.message(Command("weekly"))
    @router.message(lambda message: message.text == "📊 Неделя")
    async def weekly_report_command(message: Message) -> None:
        if not await require_owner(message):
            return
        today = datetime.now(ZoneInfo(config.timezone)).date()
        await message.answer(weekly_task_report(task_store, registry, today))

    @router.callback_query(F.data.startswith("review:"))
    async def task_review_callback(
        callback: CallbackQuery, state: FSMContext
    ) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        parts = (callback.data or "").split(":", 2)
        if len(parts) != 3 or parts[1] not in {"done", "postpone", "cancel"}:
            await callback.answer("Некорректное действие", show_alert=True)
            return
        action, task_id = parts[1], parts[2]
        task = task_store.get(task_id)
        if task is None:
            await callback.answer("Поручение не найдено", show_alert=True)
            return
        if task.status != "open":
            await callback.answer("Поручение уже закрыто", show_alert=True)
            if callback.message:
                await callback.message.edit_reply_markup(reply_markup=None)
            return
        await state.clear()
        await state.update_data(review_task_id=task.id)
        if action == "done":
            await state.set_state(TaskReview.completion_evidence)
            prompt = (
                "✅ <b>Подтвердите результат</b>\n\n"
                "Одним сообщением отправьте короткое доказательство: "
                "что проверено, ссылку или описание результата.\n\n"
                "Для отмены ввода: /cancel"
            )
        elif action == "postpone":
            await state.set_state(TaskReview.postpone_date)
            prompt = (
                "➡️ <b>Новая дата</b>\n\n"
                "Отправьте будущую дату в формате <code>ДД.ММ.ГГГГ</code>.\n"
                "Для отмены ввода: /cancel"
            )
        else:
            await state.set_state(TaskReview.cancel_reason)
            prompt = (
                "⛔ <b>Причина отмены</b>\n\n"
                "Коротко объясните, почему поручение больше не нужно.\n"
                "Для отмены ввода: /cancel"
            )
        await callback.answer()
        if callback.message:
            await callback.message.answer(prompt)

    async def review_task_from_state(
        message: Message, state: FSMContext
    ) -> OwnerTask | None:
        data = await state.get_data()
        task = task_store.get(str(data.get("review_task_id", "")))
        if task is None or task.status != "open":
            await state.clear()
            await message.answer("⚠️ Поручение уже закрыто или не найдено.")
            return None
        return task

    @router.message(TaskReview.completion_evidence)
    async def completion_evidence_received(
        message: Message, state: FSMContext
    ) -> None:
        if not await require_owner(message):
            await state.clear()
            return
        evidence = extract_task_evidence(message)
        if evidence == "/cancel":
            await state.clear()
            await message.answer("Подведение итога отменено.", reply_markup=MENU)
            return
        if not 3 <= len(evidence) <= 500:
            await message.answer("⚠️ Подтверждение должно содержать от 3 до 500 символов.")
            return
        task = await review_task_from_state(message, state)
        if task is None:
            return
        try:
            completed = task_store.complete(
                task.id,
                completed_by=message.from_user.id if message.from_user else 0,
                evidence=evidence,
            )
        except OSError:
            logger.exception("Could not persist task completion evidence")
            await message.answer("⚠️ Не удалось сохранить результат. Повторите позже.")
            return
        await state.clear()
        assert completed is not None
        await message.answer(
            "✅ <b>Результат сохранён</b>\n\n"
            f"{html.escape(completed.title)}\n"
            f"Подтверждение: {html.escape(evidence)}",
            reply_markup=MENU,
        )

    @router.message(TaskReview.postpone_date)
    async def postpone_date_received(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            await state.clear()
            return
        raw_date = (message.text or "").strip()
        if raw_date == "/cancel":
            await state.clear()
            await message.answer("Перенос отменён.", reply_markup=MENU)
            return
        try:
            new_due_date = parse_user_date(raw_date)
        except ValueError:
            await message.answer("⚠️ Дата должна быть в формате ДД.ММ.ГГГГ.")
            return
        today = datetime.now(ZoneInfo(config.timezone)).date()
        if new_due_date <= today:
            await message.answer("⚠️ Для переноса выберите дату позже сегодняшней.")
            return
        await state.update_data(postpone_date=new_due_date.isoformat())
        await state.set_state(TaskReview.postpone_reason)
        await message.answer(
            "Почему переносим поручение? Отправьте причину от 3 до 500 символов."
        )

    @router.message(TaskReview.postpone_reason)
    async def postpone_reason_received(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            await state.clear()
            return
        reason = (message.text or "").strip()
        if reason == "/cancel":
            await state.clear()
            await message.answer("Перенос отменён.", reply_markup=MENU)
            return
        task = await review_task_from_state(message, state)
        if task is None:
            return
        data = await state.get_data()
        try:
            new_due_date = date.fromisoformat(str(data.get("postpone_date", "")))
            updated = task_store.reschedule(
                task.id,
                due_date=new_due_date,
                reason=reason,
                actor_id=message.from_user.id if message.from_user else 0,
            )
        except ValueError as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}")
            return
        except OSError:
            logger.exception("Could not persist task reschedule")
            await message.answer("⚠️ Не удалось сохранить перенос. Повторите позже.")
            return
        await state.clear()
        assert updated is not None
        await message.answer(
            "➡️ <b>Поручение перенесено</b>\n\n"
            f"{html.escape(updated.title)}\n"
            f"Новый срок: <code>{format_user_date(updated.due_date)}</code>\n"
            f"Причина: {html.escape(reason)}",
            reply_markup=MENU,
        )

    @router.message(TaskReview.cancel_reason)
    async def cancel_reason_received(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            await state.clear()
            return
        reason = (message.text or "").strip()
        if reason == "/cancel":
            await state.clear()
            await message.answer("Отмена поручения прервана.", reply_markup=MENU)
            return
        task = await review_task_from_state(message, state)
        if task is None:
            return
        try:
            canceled = task_store.cancel(
                task.id,
                reason=reason,
                canceled_by=message.from_user.id if message.from_user else 0,
            )
        except ValueError as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}")
            return
        except OSError:
            logger.exception("Could not persist task cancellation")
            await message.answer("⚠️ Не удалось сохранить отмену. Повторите позже.")
            return
        await state.clear()
        assert canceled is not None
        await message.answer(
            "⛔ <b>Поручение отменено</b>\n\n"
            f"{html.escape(canceled.title)}\n"
            f"Причина: {html.escape(reason)}",
            reply_markup=MENU,
        )

    async def create_task_from_details(
        message: Message,
        raw_details: str,
    ) -> bool:
        try:
            title, due_date, criterion = parse_task_details(raw_details)
            project = registry.by_key(knowledge.active_project)
            if project is None:
                raise ValueError("Сначала выберите проект: /use ключ")
            owner_id = message.from_user.id if message.from_user else 0
            task = task_store.create(
                project_key=project.key,
                title=title,
                due_date=due_date,
                success_criterion=criterion,
                created_by=owner_id,
            )
        except (ValueError, OSError) as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}")
            return False
        await message.answer(
            "👤 <b>Моя задача создана</b>\n\n"
            + task_text(task, project.title),
            reply_markup=task_keyboard(task),
        )
        return True

    @router.message(Command("newtask"))
    @router.message(lambda message: message.text == "➕ Моя задача")
    @router.message(lambda message: message.text == "➕ Поручение")
    async def new_task_command(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        raw = (message.text or "").split(maxsplit=1)
        if len(raw) == 2 and raw[0].startswith("/newtask"):
            await create_task_from_details(message, raw[1])
            return
        await state.set_state(TaskCreation.details)
        active = registry.by_key(knowledge.active_project)
        active_title = active.title if active else knowledge.active_project
        await message.answer(
            f"👤 <b>Моя новая задача · {html.escape(active_title)}</b>\n\n"
            "Отправьте одной строкой:\n"
            "<code>Что сделать | ДД.ММ.ГГГГ | Как проверить готовность</code>\n\n"
            "Пример:\n"
            "<code>Проверить страницу оплаты | 02.08.2026 | "
            "Тестовая оплата проходит без ошибки</code>\n\n"
            "Для отмены: /cancel"
        )

    @router.message(TaskCreation.details)
    async def task_details_received(
        message: Message,
        state: FSMContext,
    ) -> None:
        if not await require_owner(message):
            await state.clear()
            return
        if (message.text or "").strip() == "/cancel":
            await state.clear()
            await message.answer("Ввод поручения отменён.", reply_markup=MENU)
            return
        if await create_task_from_details(message, message.text or ""):
            await state.clear()

    async def create_agent_task_from_details(
        message: Message,
        raw_details: str,
    ) -> bool:
        try:
            title, due_date, criterion = parse_task_details(raw_details)
            project = registry.by_key(knowledge.active_project)
            if project is None:
                raise ValueError("Сначала выберите проект: /use ключ")
            if not project.repo:
                raise ValueError(
                    "У проекта не подключён GitHub-репозиторий. "
                    "Создайте мою задачу: /newtask"
                )
            owner_id = message.from_user.id if message.from_user else 0
            task = task_store.create(
                project_key=project.key,
                title=title,
                due_date=due_date,
                success_criterion=criterion,
                created_by=owner_id,
                responsible="Codex",
                kind="agent",
            )
        except (ValueError, OSError) as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}")
            return False
        await message.answer(
            "🤖 <b>Задача агенту подготовлена</b>\n\n"
            + task_text(task, project.title)
            + "\n\nАгент изменит только отдельную ветку и создаст PR. "
            "main и production не изменяются.",
            reply_markup=agent_task_keyboard(task),
        )
        return True

    @router.message(Command("agenttask"))
    @router.message(lambda message: message.text == "🤖 Поручить агенту")
    async def new_agent_task_command(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        raw = (message.text or "").split(maxsplit=1)
        if len(raw) == 2 and raw[0].startswith("/agenttask"):
            await create_agent_task_from_details(message, raw[1])
            return
        active = registry.by_key(knowledge.active_project)
        if active is None or not active.repo:
            await message.answer(
                "⚠️ У активного проекта нет GitHub-репозитория. "
                "Бот не сможет его выполнить; создайте мою задачу: /newtask"
            )
            return
        await state.set_state(AgentTaskCreation.details)
        await message.answer(
            f"🤖 <b>Поручить Codex · {html.escape(active.title)}</b>\n\n"
            "Отправьте одной строкой:\n"
            "<code>Что улучшить | ДД.ММ.ГГГГ | Как проверить готовность</code>\n\n"
            "После этого бот ещё раз покажет условия и попросит запуск.\n"
            "Для отмены: /cancel"
        )

    @router.message(AgentTaskCreation.details)
    async def agent_task_details_received(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            await state.clear()
            return
        if (message.text or "").strip() == "/cancel":
            await state.clear()
            await message.answer("Ввод задачи агенту отменён.", reply_markup=MENU)
            return
        if await create_agent_task_from_details(message, message.text or ""):
            await state.clear()

    agent_dispatch_locks: dict[str, asyncio.Lock] = {}

    @router.callback_query(F.data.startswith("agent:"))
    async def agent_task_callback(callback: CallbackQuery) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        parts = (callback.data or "").split(":", 2)
        if len(parts) != 3 or parts[1] not in {"pick", "run", "cancel"}:
            await callback.answer("Неизвестное действие", show_alert=True)
            return
        action, task_id = parts[1], parts[2]
        task = task_store.get(task_id)
        if task is None or task.kind != "agent" or task.status != "open":
            await callback.answer("Задача агента не найдена", show_alert=True)
            return
        if action == "cancel":
            await callback.answer("Запуск отменён")
            if callback.message:
                await callback.message.edit_text(
                    "⚪️ Агент не запущен. Задача сохранена и её можно открыть снова."
                )
            return
        project = registry.by_key(task.project_key)
        if project is None or not project.repo:
            await callback.answer("Репозиторий не подключён", show_alert=True)
            return
        if action == "pick":
            await callback.answer()
            if callback.message:
                await callback.message.edit_text(
                    "🤖 <b>Подтвердите запуск Codex</b>\n\n"
                    f"Проект: {html.escape(project.title)}\n"
                    f"Задача: {html.escape(task.title)}\n"
                    f"Готово, когда: {html.escape(task.success_criterion)}\n\n"
                    "Codex получит workspace-write, но не получит "
                    "production-секреты или push в main. Результат — только PR.",
                    reply_markup=agent_confirmation_keyboard(task.id),
                )
            return
        lock = agent_dispatch_locks.setdefault(task.id, asyncio.Lock())
        async with lock:
            current = task_store.get(task.id)
            if current is None or current.agent_status == "queued":
                await callback.answer("Агент уже запущен", show_alert=True)
                return
            await callback.answer("Запускаю агента…")
            result = await client.dispatch_workflow(
                project.repo,
                "codex-agent-task.yml",
                ref="main",
                inputs={
                    "task_id": current.id,
                    "task": current.title,
                    "success_criterion": current.success_criterion,
                },
            )
            if result == "started":
                try:
                    task_store.mark_agent_queued(
                        current.id,
                        actor_id=callback.from_user.id,
                    )
                except OSError:
                    logger.exception("Could not persist dispatched agent task")
                result_text = (
                    "✅ <b>Codex запущен</b>\n\n"
                    "Он проверит репозиторий, внесёт изменения, запустит "
                    "проверки и создаст отдельный PR. main/production не изменяются."
                )
            else:
                result_text = {
                    "unauthorized": "🔒 GitHub не разрешил запуск. Ничего не изменено.",
                    "not_found": "⚠️ Coding-worker ещё не установлен в этом репозитории.",
                    "failed": "❌ GitHub временно недоступен. Ничего не изменено.",
                }[result]
            if callback.message:
                await callback.message.edit_text(result_text)

    @router.message(Command("done"))
    async def done_task_command(message: Message) -> None:
        if not await require_owner(message):
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Укажите ID: <code>/done ID</code>")
            return
        task = task_store.get(parts[1].strip())
        if task is None:
            await message.answer("⚠️ Поручение не найдено.")
            return
        if task.status != "open":
            await message.answer("⚠️ Поручение уже закрыто.")
            return
        completed = task_store.complete(
            task.id,
            completed_by=message.from_user.id if message.from_user else 0,
        )
        assert completed is not None
        await message.answer(
            "✅ Поручение выполнено:\n"
            f"<b>{html.escape(completed.title)}</b>"
        )

    @router.callback_query(F.data.startswith("task:"))
    async def task_callback(callback: CallbackQuery) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        parts = (callback.data or "").split(":", 2)
        if len(parts) != 3 or parts[1] != "done":
            await callback.answer("Неизвестное действие", show_alert=True)
            return
        task = task_store.get(parts[2])
        if task is None:
            await callback.answer("Поручение не найдено", show_alert=True)
            return
        if task.status != "open":
            await callback.answer("Поручение уже закрыто", show_alert=True)
            if callback.message:
                await callback.message.edit_reply_markup(reply_markup=None)
            return
        completed = task_store.complete(
            task.id,
            completed_by=callback.from_user.id,
        )
        assert completed is not None
        await callback.answer("Выполнено")
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)

    @router.message(Command("council"))
    @router.message(lambda message: message.text in {"🧠 Совет ИИ", "🧠 Совет директоров"})
    async def council_command(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        await state.clear()
        await message.answer(
            "🧠 <b>Выберите режим совета</b>\n\n"
            "🆓 Без расходов — встроенные роли и текущие проверки.\n"
            "⚡ API — выбранная модель анализирует задачу в облаке; "
            "перед расходом токенов потребуется подтверждение.\n"
            "💳 Подписка — подготовлю промпт для ручного использования "
            "ChatGPT, Claude или Gemini.\n\n"
            "⭐ Для работы при выключенном компьютере выбирайте API.",
            reply_markup=council_mode_keyboard(),
        )

    @router.callback_query(F.data.startswith("councilmode:"))
    async def council_mode_callback(
        callback: CallbackQuery, state: FSMContext
    ) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        mode = (callback.data or "").split(":", 1)[-1]
        if mode == "builtin":
            await state.set_state(OwnerCouncil.task)
            text = (
                "🆓 <b>Опишите задачу для встроенного совета</b>\n\n"
                "Например: «Проверь IQ Barakah перед релизом».\n"
                "Для отмены: /cancel"
            )
        elif mode == "subscriptions":
            await state.set_state(SubscriptionCouncil.task)
            text = (
                "💳 <b>Опишите задачу</b>\n\n"
                "Я подготовлю единый промпт, который вы сможете вручную "
                "использовать в оплаченной подписке.\nДля отмены: /cancel"
            )
        elif mode == "api":
            configured = config.ai_provider_secrets.configured_providers()
            await callback.answer()
            if callback.message:
                if configured:
                    await callback.message.answer(
                        "⚡ <b>Выберите API-модель</b>\n\n"
                        "Токены начнут расходоваться только после описания задачи "
                        "и отдельного подтверждения.",
                        reply_markup=api_provider_keyboard(configured),
                    )
                else:
                    await callback.message.answer(
                        "⚠️ Ни один AI API ещё не подключён. "
                        "Добавьте ключи как секреты Amvera и перезапустите контейнер."
                    )
            return
        else:
            await callback.answer("Неизвестный режим", show_alert=True)
            return
        await callback.answer()
        if callback.message:
            await callback.message.answer(text)

    @router.callback_query(F.data.startswith("aipick:"))
    async def api_pick_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        provider_key = (callback.data or "").split(":", 1)[-1]
        if provider_key == "cancel":
            await state.clear()
            await callback.answer("Отменено")
            return
        configured = config.ai_provider_secrets.configured_providers()
        if provider_key == "multi":
            await state.clear()
            await state.update_data(mode="multi", selected=[])
            await callback.answer()
            if callback.message:
                await callback.message.edit_reply_markup(
                    reply_markup=multi_provider_keyboard(configured, ())
                )
            return
        if provider_key == "all":
            await state.set_state(ApiCouncil.task)
            await state.update_data(mode="all", providers=list(configured))
            await callback.answer()
            if callback.message:
                await callback.message.answer(
                    f"🏛 <b>Полный совет: {len(configured)} моделей</b>\n\n"
                    "Опишите задачу. Перед запуском я покажу количество "
                    "API-запросов и попрошу подтверждение.\nДля отмены: /cancel"
                )
            return
        if provider_key == "auto":
            await state.set_state(ApiCouncil.task)
            await state.update_data(mode="auto", providers=[])
            await callback.answer()
            if callback.message:
                await callback.message.answer(
                    "⭐ <b>Автовыбор модели</b>\n\n"
                    "Опишите задачу. Бот выберет одну подходящую модель и "
                    "покажет её до подтверждения.\nДля отмены: /cancel"
                )
            return
        provider = AI_PROVIDERS_BY_KEY.get(provider_key)
        if (
            provider is None
            or not config.ai_provider_secrets.for_provider(provider_key)
        ):
            await callback.answer("Провайдер не подключён", show_alert=True)
            return
        await state.set_state(ApiCouncil.task)
        await state.update_data(mode="single", providers=[provider_key])
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                f"⚡ <b>{html.escape(provider.title)}</b>\n\n"
                "Опишите задачу от 5 до 800 символов. После этого я ещё раз "
                "попрошу подтвердить расход API-токенов.\nДля отмены: /cancel"
            )

    @router.callback_query(F.data.startswith("aimulti:"))
    async def api_multi_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        action = parts[1] if len(parts) > 1 else ""
        configured = config.ai_provider_secrets.configured_providers()
        data = await state.get_data()
        selected = [
            key for key in data.get("selected", []) if key in configured
        ]
        if action == "cancel":
            await state.clear()
            await callback.answer("Отменено")
            return
        if action == "toggle" and len(parts) == 3:
            key = parts[2]
            if key not in configured:
                await callback.answer("Провайдер не подключён", show_alert=True)
                return
            if key in selected:
                selected.remove(key)
            else:
                selected.append(key)
            await state.update_data(selected=selected)
            await callback.answer()
            if callback.message:
                await callback.message.edit_reply_markup(
                    reply_markup=multi_provider_keyboard(
                        configured, tuple(selected)
                    )
                )
            return
        if action == "done":
            if not 2 <= len(selected) <= 4:
                await callback.answer(
                    "Выберите от 2 до 4 моделей", show_alert=True
                )
                return
            await state.set_state(ApiCouncil.task)
            await state.update_data(
                mode="multi", providers=selected, selected=[]
            )
            await callback.answer()
            if callback.message:
                names = ", ".join(provider_titles(tuple(selected)))
                await callback.message.answer(
                    f"👥 <b>Выбраны:</b> {html.escape(names)}\n\n"
                    "Опишите задачу. После этого потребуется подтверждение.\n"
                    "Для отмены: /cancel"
                )
            return
        await callback.answer("Некорректный выбор", show_alert=True)

    @router.message(SubscriptionCouncil.task)
    async def subscription_council_task(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        task = (message.text or "").strip()
        if task == "/cancel":
            await state.clear()
            await message.answer("Отменено.", reply_markup=MENU)
            return
        if not 5 <= len(task) <= 800:
            await message.answer("⚠️ Опишите задачу текстом от 5 до 800 символов.")
            return
        project = knowledge.resolve(task, registry.all())
        prompt = (
            "Выступи как совет CEO, CTO, CPO, CMO, CCO, CFO, CISO и "
            "критик. Дай вердикт, три варианта, рекомендацию, риски и "
            "следующий безопасный шаг.\n\n"
            f"{knowledge.ai_task(project, task)}"
        )
        await state.clear()
        await message.answer(
            "💳 <b>Промпт для вашей подписки</b>\n\n"
            f"<b>Проект:</b> {html.escape(project.title)}\n\n"
            f"<pre>{html.escape(prompt)}</pre>\n\n"
            "Скопируйте промпт и откройте нужный сервис. Этот режим не "
            "работает автономно при закрытом компьютере.",
            reply_markup=subscription_links_keyboard(),
        )

    @router.message(ApiCouncil.task)
    async def api_council_task(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        task = (message.text or "").strip()
        if task == "/cancel":
            await state.clear()
            await message.answer("Отменено.", reply_markup=MENU)
            return
        if not 5 <= len(task) <= 800:
            await message.answer("⚠️ Опишите задачу текстом от 5 до 800 символов.")
            return
        data = await state.get_data()
        mode = str(data.get("mode", "single"))
        configured = config.ai_provider_secrets.configured_providers()
        providers = tuple(
            key for key in data.get("providers", []) if key in configured
        )
        if mode == "auto":
            auto_provider = choose_auto_provider(task, configured)
            providers = (auto_provider,) if auto_provider else ()
        if not providers:
            await state.clear()
            await message.answer("Провайдеры не найдены. Начните заново: /council")
            return
        project = knowledge.resolve(task, registry.all())
        ai_task = knowledge.ai_task(project, task)
        names = ", ".join(provider_titles(providers))
        judge_key = choose_judge(configured) if len(providers) > 1 else ""
        request_count = len(providers) + (1 if judge_key else 0)
        await state.update_data(
            task=task,
            ai_task=ai_task,
            project=project.key,
            providers=list(providers),
            judge=judge_key,
        )
        judge_note = (
            f"\nМодель-судья: {AI_PROVIDERS_BY_KEY[judge_key].title}."
            if judge_key
            else ""
        )
        await message.answer(
            f"⚡ <b>Запустить AI-совет через API?</b>\n\n"
            f"<b>Модели:</b> {html.escape(names)}\n"
            f"<b>Проект:</b> {html.escape(project.title)}\n"
            f"<b>API-запросов:</b> {request_count}.{html.escape(judge_note)}\n"
            f"<b>Задача:</b> {html.escape(task)}\n\n"
            "Запрос будет передан внешнему AI-провайдеру и израсходует "
            "API-токены. Код и production автоматически не изменяются.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Запустить",
                            callback_data="airun:start",
                        ),
                        InlineKeyboardButton(
                            text="⛔ Отмена",
                            callback_data="airun:cancel",
                        ),
                    ]
                ]
            ),
        )

    @router.callback_query(F.data.startswith("airun:"))
    async def api_run_callback(callback: CallbackQuery, state: FSMContext) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        action = (callback.data or "").split(":", 1)[-1]
        if action == "cancel":
            await state.clear()
            await callback.answer("Отменено")
            if callback.message:
                await callback.message.edit_reply_markup(reply_markup=None)
            return
        data = await state.get_data()
        configured = config.ai_provider_secrets.configured_providers()
        providers = tuple(
            key for key in data.get("providers", []) if key in configured
        )
        if action != "start" or not providers or not data.get("ai_task"):
            await callback.answer("Запрос устарел. Начните заново.", show_alert=True)
            return
        await callback.answer("AI анализирует задачу…")
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(
                f"⏳ Запрос отправлен моделям: "
                f"{html.escape(', '.join(provider_titles(providers)))}…"
            )
        responses = await asyncio.gather(
            *(
                ask_ai(
                    session,
                    config.ai_provider_secrets,
                    provider_key,
                    str(data["ai_task"]),
                )
                for provider_key in providers
            ),
            return_exceptions=True,
        )
        successful = tuple(
            (provider_key, response)
            for provider_key, response in zip(providers, responses)
            if isinstance(response, str) and response.strip()
        )
        failed = tuple(
            provider_key
            for provider_key, response in zip(providers, responses)
            if isinstance(response, Exception)
        )
        if not successful:
            result = (
                "⚠️ Ни один AI-провайдер не ответил. Проверьте баланс, "
                "ключи и доступность выбранных моделей."
            )
            result_title = "AI-совет"
        elif len(successful) == 1:
            result = successful[0][1]
            result_title = AI_PROVIDERS_BY_KEY[successful[0][0]].title
        else:
            judge_key = str(data.get("judge", ""))
            try:
                result = await ask_ai(
                    session,
                    config.ai_provider_secrets,
                    judge_key,
                    synthesis_task(str(data["ai_task"]), successful),
                )
                result_title = (
                    f"Итог совета · судья "
                    f"{AI_PROVIDERS_BY_KEY[judge_key].title}"
                )
            except Exception:
                logger.exception("AI council synthesis failed")
                result_title = "Ответы совета без синтеза"
                result = "\n\n".join(
                    f"{AI_PROVIDERS_BY_KEY[key].title}:\n{text[:900]}"
                    for key, text in successful
                )
        if failed:
            failed_names = ", ".join(provider_titles(failed))
            result += f"\n\nНе ответили: {failed_names}."
        await state.clear()
        if callback.message:
            await callback.message.answer(
                f"⚡ <b>{html.escape(result_title)}</b>\n\n"
                f"{html.escape(result[:3500])}",
                reply_markup=MENU,
            )

    @router.message(OwnerCouncil.task)
    async def council_task(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        task = (message.text or "").strip()
        if task == "/cancel":
            await state.clear()
            await message.answer("Совет отменён.", reply_markup=MENU)
            return
        if not 5 <= len(task) <= 800:
            await message.answer(
                "⚠️ Опишите задачу текстом от 5 до 800 символов."
            )
            return
        project = knowledge.resolve(task, registry.all())
        site, runs = await asyncio.gather(
            client.site_status(project),
            (
                client.workflow_runs(project.repo, limit=1)
                if project.repo
                else asyncio.sleep(0, result=None)
            ),
        )
        latest = runs[0] if runs else {}
        context = CouncilContext(
            project=project,
            site_ok=site.ok,
            status_code=site.status_code,
            latest_workflow=latest.get("name"),
            latest_status=latest.get("conclusion") or latest.get("status"),
        )
        views = council_views(task, context)
        lines = [
            "🧠 <b>Совет директоров</b>",
            f"<b>Проект:</b> {html.escape(project.title)}",
            f"<b>Задача:</b> {html.escape(task)}",
            "",
        ]
        for view in views:
            lines.append(
                f"<b>{html.escape(view.role)}</b> · {html.escape(view.focus)}\n"
                f"{html.escape(view.recommendation)}"
            )
        lines.extend(["", "<b>Рекомендация совета</b>"])
        lines.extend(
            html.escape(item) for item in executive_recommendation(context)
        )
        lines.extend(
            [
                "",
                "Выберите следующий шаг. Read-only проверка запускается сразу; "
                "изменения и production потребуют отдельного разрешения.",
            ]
        )
        await state.clear()
        await message.answer(
            "\n\n".join(lines),
            reply_markup=council_keyboard(project.key),
        )

    @router.callback_query(F.data.startswith("council:"))
    async def council_callback(callback: CallbackQuery) -> None:
        owner_id = callback.from_user.id
        if owner_id not in config.owner_ids:
            logger.warning("Rejected council callback from Telegram user %s", owner_id)
            await callback.answer("Нет доступа", show_alert=True)
            return
        parts = (callback.data or "").split(":", 2)
        if len(parts) != 3:
            await callback.answer("Некорректный запрос", show_alert=True)
            return
        action, project_key = parts[1], parts[2]
        project = registry.by_key(project_key)
        if project is None:
            await callback.answer("Проект не найден", show_alert=True)
            return
        if action == "cancel":
            await callback.answer("Отменено")
            if callback.message:
                await callback.message.edit_reply_markup(reply_markup=None)
            return
        if action == "inspect":
            await callback.answer("Проверяю…")
            if callback.message:
                await callback.message.answer(
                    await project_summary(client, project),
                    disable_web_page_preview=True,
                )
            return
        if action == "pwa" and project.key == "iqbarakah":
            await callback.answer("Показываю безопасный следующий шаг")
            if callback.message:
                await callback.message.answer(
                    "🧪 <b>Разрешить подготовку PWA-релиза?</b>\n\n"
                    "Будут выполнены только сборка и проверки. "
                    "Публикация production потребует ещё одного отдельного решения.",
                    reply_markup=pwa_release_keyboard(),
                )
            return
        await callback.answer("Действие не разрешено", show_alert=True)

    @router.message(Command("projects"))
    @router.message(lambda message: message.text == "📂 Проекты")
    async def projects_command(message: Message) -> None:
        if not await require_owner(message):
            return
        summaries = await asyncio.gather(
            *(project_summary(client, project) for project in registry.all())
        )
        await message.answer("\n\n".join(summaries), disable_web_page_preview=True)

    @router.message(Command("library"))
    @router.message(lambda message: message.text == "📚 Библиотека проектов")
    async def library_command(message: Message) -> None:
        if not await require_owner(message):
            return
        lines = ["📚 <b>Библиотека проектов</b>"]
        for project in registry.all():
            marker = "✅" if project.key == knowledge.active_project else "▫️"
            brief = knowledge.brief(project.key)
            lines.append(
                f"{marker} <b>{html.escape(project.title)}</b> "
                f"(<code>{html.escape(project.key)}</code>)\n"
                f"{html.escape(brief[:500])}"
            )
        lines.append(
            "\nАктивный проект используется, когда в короткой задаче не указано "
            "название. Переключение: <code>/use mizanlife</code>.\n"
            "Обновление паспорта: <code>/brief описание проекта</code>."
        )
        await message.answer("\n\n".join(lines))

    @router.message(Command("use"))
    async def use_project_command(message: Message) -> None:
        if not await require_owner(message):
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Укажите ключ, например: <code>/use mizanlife</code>")
            return
        key = parts[1].strip().lower()
        project = registry.by_key(key)
        if project is None:
            await message.answer("⚠️ Проект с таким ключом не найден.")
            return
        knowledge.set_active(project.key, registry.all())
        await message.answer(
            f"✅ Активный проект: <b>{html.escape(project.title)}</b>.\n"
            "Теперь можно давать короткие задачи без повторения названия."
        )

    @router.message(Command("brief"))
    async def update_brief_command(message: Message) -> None:
        if not await require_owner(message):
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(
                "После команды одним сообщением укажите: что это, для кого, "
                "основные функции и чем проект не является.\n\n"
                "Пример: <code>/brief Планировщик для предпринимателей...</code>"
            )
            return
        project = registry.by_key(knowledge.active_project)
        if project is None:
            await message.answer("⚠️ Сначала выберите проект: /use ключ")
            return
        try:
            knowledge.set_brief(project.key, parts[1])
        except (ValueError, OSError) as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}")
            return
        await message.answer(
            f"✅ Паспорт <b>{html.escape(project.title)}</b> обновлён.\n"
            "Следующие AI-запросы будут использовать новое описание."
        )

    for command, project in PROJECTS_BY_KEY.items():
        async def handler(
            message: Message,
            selected_project=project,
        ) -> None:
            if not await require_owner(message):
                return
            knowledge.set_active(selected_project.key, registry.all())
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

    @router.message(Command("automation"))
    @router.message(lambda message: message.text == "☁️ Автоматизация")
    async def automation_center(message: Message) -> None:
        if not await require_owner(message):
            return
        await message.answer(
            "☁️ <b>Центр автоматизации</b>\n\n"
            "Выберите разрешённый облачный сценарий. Preview не публикуется "
            "в магазин. Production после запуска отдельно запросит разрешение "
            "в Telegram.\n\n"
            "Mini App здесь пока отсутствует: сначала ему нужен такой же "
            "защитный шлюз.",
            reply_markup=automation_center_keyboard(),
        )

    @router.callback_query(F.data.startswith("auto:"))
    async def automation_callback(callback: CallbackQuery) -> None:
        if callback.from_user.id not in config.owner_ids:
            await callback.answer("Нет доступа", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        action = parts[1] if len(parts) > 1 else ""
        if action == "cancel":
            await callback.answer("Отменено")
            if callback.message:
                await callback.message.edit_text(
                    "⚪️ Облачный запуск отменён. Ничего не запускалось."
                )
            return
        if action == "pwa":
            await callback.answer()
            if callback.message:
                await callback.message.edit_text(
                    "🧪 <b>Подготовить PWA-релиз IQ Barakah?</b>\n\n"
                    "Сначала пройдут проверки. Перед production бот запросит "
                    "отдельное разрешение.",
                    reply_markup=pwa_release_keyboard(),
                )
            return
        if len(parts) != 4 or action not in {"pick", "run"}:
            await callback.answer("Некорректный сценарий", show_alert=True)
            return
        platform, profile = parts[2], parts[3]
        if platform not in {"android", "ios"} or profile not in {
            "preview",
            "production",
        }:
            await callback.answer("Сценарий не разрешён", show_alert=True)
            return
        if action == "pick":
            await callback.answer()
            warning = (
                "После сборки появится release-кандидат; публикации в магазин "
                "не произойдёт без отдельного действия."
                if profile == "production"
                else "Будет создана тестовая сборка; production не изменится."
            )
            if callback.message:
                await callback.message.edit_text(
                    "☁️ <b>Подтвердите облачный запуск</b>\n\n"
                    f"Платформа: <b>{platform.upper()}</b>\n"
                    f"Профиль: <b>{profile}</b>\n\n{warning}",
                    reply_markup=automation_confirmation_keyboard(platform, profile),
                )
            return

        await callback.answer("Проверяю очередь…")
        runs = await client.workflow_runs("iq-barakah", limit=10)
        if runs is None:
            result_text = "❌ Не удалось проверить GitHub. Ничего не запущено."
        elif any(
            run.get("name") == "Build mobile release"
            and run.get("status") in {"queued", "in_progress", "waiting", "pending"}
            for run in runs
        ):
            result_text = "⏳ Мобильная сборка уже выполняется. Дубликат не создан."
        else:
            result = await client.dispatch_workflow(
                "iq-barakah",
                "release-mobile.yml",
                ref="main",
                inputs={"platform": platform, "profile": profile},
            )
            result_text = {
                "started": (
                    "✅ Облачная сборка запущена.\n\n"
                    + (
                        "Перед production бот пришлёт отдельный запрос "
                        "«Разрешить / Отклонить»."
                        if profile == "production"
                        else "Результат появится в Expo/EAS; production не меняется."
                    )
                ),
                "unauthorized": "🔒 GitHub не разрешил запуск. Ничего не запущено.",
                "not_found": "❌ Workflow не найден. Ничего не запущено.",
                "failed": "❌ GitHub временно недоступен. Ничего не запущено.",
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
            validate_project(data["key"], data["title"], data["url"], repo)
        except ValueError as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}\nПопробуйте ещё раз.")
            return
        await state.update_data(repo=repo)
        await state.set_state(AddProject.brief)
        await message.answer(
            "📚 <b>Коротко объясните проект одним сообщением</b>\n\n"
            "Укажите: что это, для кого, основные функции и чем проект точно "
            "не является. От 20 до 2000 символов.\n\n"
            "Пример: «Сервис для владельцев малого бизнеса: ведёт клиентов и "
            "задачи. Не является интернет-магазином»."
        )

    @router.message(AddProject.brief)
    async def add_project_brief(message: Message, state: FSMContext) -> None:
        if not await require_owner(message):
            return
        brief = (message.text or "").strip()
        data = await state.get_data()
        try:
            project = validate_project(
                data["key"],
                data["title"],
                data["url"],
                data.get("repo"),
            )
            knowledge.set_brief(project.key, brief)
            registry.add(project)
            knowledge.set_active(project.key, registry.all())
        except (ValueError, OSError) as exc:
            await message.answer(f"⚠️ {html.escape(str(exc))}\nПопробуйте ещё раз.")
            return
        await state.clear()
        await message.answer(
            f"✅ Проект <b>{html.escape(project.title)}</b> добавлен.\n"
            "Паспорт сохранён в библиотеке, а проект выбран активным.",
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
        sent = await message.answer(
            approval_text(approval),
            reply_markup=approval_keyboard(approval),
        )
        approval_store.add_telegram_message(
            approval.id,
            chat_id=sent.chat.id,
            message_id=sent.message_id,
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
        approval = approval_store.get(parts[2])
        if approval is None:
            await callback.answer("Запрос не найден", show_alert=True)
            return
        wants_approval = parts[1] == "approve"
        if (
            approval.status == "pending"
            and approval.github_repository
            and approval.github_run_id
        ):
            review = "not_found"
            for attempt in range(4):
                review = await client.review_pending_deployment(
                    approval.github_repository,
                    approval.github_run_id,
                    approved=wants_approval,
                )
                if review != "not_found" or attempt == 3:
                    break
                await asyncio.sleep(3)
            if review == "unauthorized":
                await callback.answer(
                    "GitHub-токену нужно право Deployments: write",
                    show_alert=True,
                )
                return
            if review == "not_found":
                await callback.answer(
                    "GitHub ещё готовит запрос. Повторите через несколько секунд.",
                    show_alert=True,
                )
                return
            if review == "failed":
                await callback.answer(
                    "GitHub временно недоступен. Решение не применено.",
                    show_alert=True,
                )
                return
            if review == "already_started" and not wants_approval:
                await callback.answer(
                    "Релиз уже разрешён через GitHub; отклонить поздно.",
                    show_alert=True,
                )
                return
        approval = approval_store.decide(
            parts[2],
            approved=wants_approval,
            owner_id=owner_id,
            source="telegram",
        )
        assert approval is not None
        callback_answers = {
            "approved": "Разрешено",
            "rejected": "Отклонено",
            "expired": "Срок запроса истёк",
            "pending": "Решение не сохранено",
        }
        await callback.answer(callback_answers[approval.status])
        await refresh_approval_messages(callback.bot, approval)

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
            github_repository = payload.get("github_repository")
            github_run_id = payload.get("github_run_id")
            if github_repository is not None:
                github_repository = str(github_repository).strip()
            if github_run_id is not None:
                github_run_id = int(github_run_id)
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
            or (
                github_repository is not None
                and not 2 <= len(github_repository) <= 100
            )
            or (github_run_id is not None and github_run_id <= 0)
        ):
            raise web.HTTPBadRequest(text="invalid request")
        approval, created = approval_store.create(
            idempotency_key=idempotency_key,
            project=project,
            action=action,
            description=description,
            risk=risk,
            ttl_minutes=ttl_minutes,
            github_repository=github_repository,
            github_run_id=github_run_id,
        )
        if approval.status == "pending" and approval.notified_at is None:
            delivered = False
            for owner_id in config.owner_ids:
                try:
                    sent = await bot.send_message(
                        owner_id,
                        approval_text(approval),
                        reply_markup=approval_keyboard(approval),
                    )
                    approval = (
                        approval_store.add_telegram_message(
                            approval.id,
                            chat_id=sent.chat.id,
                            message_id=sent.message_id,
                        )
                        or approval
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

    async def decide_approval(request: web.Request) -> web.Response:
        if not approval_auth_ok(request, config.approval_api_secret):
            raise web.HTTPUnauthorized()
        approval = approval_store.get(request.match_info["approval_id"])
        if approval is None:
            raise web.HTTPNotFound()
        try:
            payload = await request.json()
            status = str(payload["status"])
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            aiohttp.ContentTypeError,
        ):
            raise web.HTTPBadRequest(text="invalid request") from None
        if status not in {"approved", "rejected"}:
            raise web.HTTPBadRequest(text="invalid request")
        approval = approval_store.decide(
            approval.id,
            approved=status == "approved",
            owner_id=None,
            source="github",
        )
        assert approval is not None
        await refresh_approval_messages(bot, approval)
        return web.json_response(
            {
                "id": approval.id,
                "status": approval.status,
                "decided_at": approval.decided_at,
            }
        )

    app.router.add_post("/approvals", create_approval)
    app.router.add_get("/approvals/{approval_id}", get_approval)
    app.router.add_post("/approvals/{approval_id}/decision", decide_approval)
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
        knowledge = ProjectKnowledgeLibrary(config.data_dir)
        approval_store = ApprovalStore(config.data_dir)
        task_store = TaskStore(config.data_dir)
        day_plan_store = DayPlanStore(config.data_dir)
        idea_store = IdeaStore(config.data_dir)
        bot = Bot(
            config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            await bot.set_my_commands(BOT_COMMANDS)
        except Exception:
            logger.exception(
                "Could not refresh Telegram command menu; bot will continue"
            )
        dispatcher = Dispatcher()
        dispatcher.include_router(
            build_router(
                config,
                session,
                client,
                registry,
                knowledge,
                approval_store,
                task_store,
                day_plan_store,
                idea_store,
            )
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
                config.morning_report_hour,
                config.evening_report_hour,
                config.weekly_report_weekday,
                config.weekly_report_hour,
                config.timezone,
                config.github_token_expires_at,
                task_store,
                approval_store,
                lambda states, today: send_automatic_day_plan(
                    bot,
                    config.owner_ids,
                    states,
                    registry,
                    task_store,
                    day_plan_store,
                    knowledge.active_project,
                    today,
                ),
            )
        )
        approval_reconciliation_task = asyncio.create_task(
            approval_reconciliation_loop(bot, client, approval_store)
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
            approval_reconciliation_task.cancel()
            await asyncio.gather(
                monitor_task,
                approval_reconciliation_task,
                return_exceptions=True,
            )
            await health_runner.cleanup()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
