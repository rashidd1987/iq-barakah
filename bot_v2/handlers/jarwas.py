"""AI-ментор Джарвас."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot_v2.keyboards import kb_jarwas_actions
from bot_v2.services import jarwas as jarwas_svc

router = Router(name="jarwas")


class JarwasStates(StatesGroup):
    chatting = State()


@router.callback_query(F.data == "jarwas_start")
async def cb_jarwas_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(JarwasStates.chatting)
    await state.update_data(history=[])
    await call.message.answer(
        "🤖 *Джарвас — AI-ментор IQ Barakah*\n\n"
        "Привет! Я здесь чтобы помочь тебе в рамках программы IQ Barakah.\n"
        "Задай любой вопрос о программе, своём прогрессе или о том, с чего начать. 🌿\n\n"
        "_Для завершения нажми кнопку ниже._",
        parse_mode="Markdown",
        reply_markup=kb_jarwas_actions(),
    )


@router.message(JarwasStates.chatting)
async def msg_jarwas(message: Message, state: FSMContext):
    data = await state.get_data()
    history = data.get("history", [])

    await message.bot.send_chat_action(message.chat.id, "typing")

    response = await jarwas_svc.ask_jarwas(history, message.text or "")
    clean_text, btn_type = jarwas_svc.parse_btn_marker(response)

    history.append({"role": "user", "content": message.text})
    history.append({"role": "assistant", "content": clean_text})
    await state.update_data(history=history[-20:])

    await message.answer(
        clean_text,
        parse_mode="Markdown",
        reply_markup=kb_jarwas_actions(btn_type),
    )


@router.callback_query(F.data == "jarwas_end")
async def cb_jarwas_end(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    await call.message.answer("БаракАллах фикум. Напиши /start чтобы вернуться в меню. 🌿")
