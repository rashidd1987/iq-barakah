"""Хендлер /start и главное меню."""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.repositories import UserRepo
from bot_v2.keyboards import kb_language, kb_main_menu
from bot_v2.config import Config
from bot_v2.services.i18n import language_name, normalize_lang, t

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, config: Config, state: FSMContext):
    await state.clear()
    user = message.from_user
    repo = UserRepo(session)
    db_user, _ = await repo.get_or_create(
        user_id=user.id,
        name=user.full_name or user.first_name or "Участник",
        username=user.username,
        language_code=normalize_lang(user.language_code),
    )

    lang = db_user.language_code or normalize_lang(user.language_code)
    greeting = t(lang, "start.greeting", name=db_user.name)

    await message.answer(f"Меню обновлено · {config.version}", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        greeting,
        parse_mode="Markdown",
        reply_markup=kb_main_menu(config.miniapp_url, config.ship_url, lang),
    )


@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, session: AsyncSession, config: Config):
    await call.answer()
    repo = UserRepo(session)
    user = await repo.get(call.from_user.id)
    lang = user.language_code if user else normalize_lang(call.from_user.language_code)
    await call.message.edit_reply_markup(
        reply_markup=kb_main_menu(config.miniapp_url, config.ship_url, lang)
    )


@router.message(Command("language"))
async def cmd_language(message: Message, session: AsyncSession):
    repo = UserRepo(session)
    user, _ = await repo.get_or_create(
        user_id=message.from_user.id,
        name=message.from_user.full_name or message.from_user.first_name or "Участник",
        username=message.from_user.username,
        language_code=normalize_lang(message.from_user.language_code),
    )
    await message.answer(t(user.language_code, "language.choose"), reply_markup=kb_language())


@router.callback_query(F.data == "language")
async def cb_language(call: CallbackQuery, session: AsyncSession):
    repo = UserRepo(session)
    user = await repo.get(call.from_user.id)
    lang = user.language_code if user else normalize_lang(call.from_user.language_code)
    await call.answer()
    await call.message.answer(t(lang, "language.choose"), reply_markup=kb_language())


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_language(call: CallbackQuery, session: AsyncSession, config: Config):
    lang = normalize_lang(call.data.split(":", 1)[1])
    repo = UserRepo(session)
    user, _ = await repo.get_or_create(
        user_id=call.from_user.id,
        name=call.from_user.full_name or call.from_user.first_name or "Участник",
        username=call.from_user.username,
        language_code=lang,
    )
    await repo.update(user.id, language_code=lang)
    await call.answer(t(lang, "language.saved", language=language_name(lang)), show_alert=False)
    await call.message.answer(
        t(lang, "language.saved", language=language_name(lang)),
        reply_markup=kb_main_menu(config.miniapp_url, config.ship_url, lang),
        parse_mode="Markdown",
    )
