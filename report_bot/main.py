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
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
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
from report_bot.knowledge import ProjectKnowledgeLibrary
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

BOT_COMMANDS = (
    BotCommand(command="projects", description="Все проекты"),
    BotCommand(command="iqbarakah", description="Статус IQ Barakah"),
    BotCommand(command="mizanlife", description="Статус Mizan Life"),
    BotCommand(command="mizanos", description="Статус Mizan OS"),
    BotCommand(command="status", description="Состояние автоматизаций"),
    BotCommand(command="council", description="Совет ролей по задаче"),
    BotCommand(command="library", description="Библиотека проектов"),
    BotCommand(command="use", description="Выбрать активный проект"),
    BotCommand(command="brief", description="Обновить паспорт проекта"),
    BotCommand(command="releases", description="Последние релизы"),
    BotCommand(command="errors", description="Последние ошибки"),
    BotCommand(command="releasepwa", description="Подготовить PWA-релиз"),
    BotCommand(command="help", description="Справка по командам"),
)

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧠 Совет ИИ")],
        [KeyboardButton(text="📚 Библиотека проектов")],
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
            "/council — бесплатный, API или подписной совет\n"
            "/library — паспорта и активный проект\n"
            "/use ключ — выбрать проект для коротких задач\n"
            "/brief текст — обновить паспорт активного проекта\n"
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
                config.evening_report_hour,
                config.timezone,
                config.github_token_expires_at,
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
