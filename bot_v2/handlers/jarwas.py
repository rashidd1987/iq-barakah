"""AI-ментор Джарвас."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.repositories import UserRepo
from bot_v2.keyboards import kb_jarwas_actions_i18n
from bot_v2.services.i18n import t
from bot_v2.services import jarwas as jarwas_svc

router = Router(name="jarwas")


class JarwasStates(StatesGroup):
    chatting = State()


@router.callback_query(F.data == "jarwas_start")
async def cb_jarwas_start(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await UserRepo(session).get(call.from_user.id)
    lang = user.language_code if user else "ru"
    is_female = user.is_female if user else None
    await call.answer()
    await state.set_state(JarwasStates.chatting)
    await state.update_data(history=[], lang=lang, is_female=is_female)
    await call.message.answer(
        t(lang, "jarwas.start"),
        parse_mode="Markdown",
        reply_markup=kb_jarwas_actions_i18n(lang=lang),
    )


@router.message(JarwasStates.chatting)
async def msg_jarwas(message: Message, state: FSMContext):
    data = await state.get_data()
    history = data.get("history", [])
    lang = data.get("lang", "ru")
    is_female = data.get("is_female")

    await message.bot.send_chat_action(message.chat.id, "typing")

    response = await jarwas_svc.ask_jarwas(history, message.text or "", is_female=is_female)
    clean_text, btn_type = jarwas_svc.parse_btn_marker(response)

    history.append({"role": "user", "content": message.text})
    history.append({"role": "assistant", "content": clean_text})
    await state.update_data(history=history[-20:])

    await message.answer(
        clean_text,
        parse_mode="Markdown",
        reply_markup=kb_jarwas_actions_i18n(btn_type, lang),
    )


@router.callback_query(F.data == "jarwas_end")
async def cb_jarwas_end(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await call.answer()
    await state.clear()
    await call.message.answer(t(lang, "jarwas.end"))


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
