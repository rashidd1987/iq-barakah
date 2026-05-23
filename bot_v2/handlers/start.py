"""Хендлер /start и главное меню."""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.repositories import UserRepo
from bot_v2.keyboards import kb_main_menu
from bot_v2.config import Config

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
    )

    greeting = (
        "Ас-саляму алейкум, *{}*! 🌿\n\n"
        "Добро пожаловать в IQ Barakah — программу для мусульманина "
        "который хочет выстроить жизнь с Аллахом в центре.\n\n"
        "Выбери с чего начать 👇"
    ).format(db_user.name)

    await message.answer(
        greeting,
        parse_mode="Markdown",
        reply_markup=kb_main_menu(config.miniapp_url, config.ship_url),
    )


@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, config: Config):
    await call.answer()
    await call.message.edit_reply_markup(
        reply_markup=kb_main_menu(config.miniapp_url, config.ship_url)
    )
