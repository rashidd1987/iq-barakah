"""AI-ментор Джарвас."""
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.repositories import ParticipantRepo, UserRepo
from bot_v2.keyboards import kb_jarwas_actions_i18n
from bot_v2.services.i18n import t
from bot_v2.services import jarwas as jarwas_svc

router = Router(name="jarwas")


class JarwasStates(StatesGroup):
    chatting = State()


@router.callback_query(F.data == "jarwas_start")
async def cb_jarwas_start(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    uid = call.from_user.id
    lang = await _user_lang(session, uid)
    await call.answer()
    await state.set_state(JarwasStates.chatting)

    participant = await ParticipantRepo(session).get(uid)
    user = await UserRepo(session).get(uid)
    profile = _build_profile(user)

    await state.update_data(
        history=[],
        lang=lang,
        level=participant.level if participant else None,
        week=participant.week if participant else None,
        profile=profile,
    )
    await call.message.answer(
        t(lang, "jarwas.start"),
        parse_mode="Markdown",
        reply_markup=kb_jarwas_actions_i18n(lang=lang),
    )


@router.message(Command("jarwas"))
async def cmd_jarwas(message: Message, state: FSMContext, session: AsyncSession):
    uid = message.from_user.id
    lang = await _user_lang(session, uid)
    participant = await ParticipantRepo(session).get(uid)
    user = await UserRepo(session).get(uid)
    profile = _build_profile(user)

    await state.set_state(JarwasStates.chatting)
    await state.update_data(
        history=[],
        lang=lang,
        level=participant.level if participant else None,
        week=participant.week if participant else None,
        profile=profile,
    )
    await message.answer(
        t(lang, "jarwas.start"),
        parse_mode="Markdown",
        reply_markup=kb_jarwas_actions_i18n(lang=lang),
    )


@router.message(JarwasStates.chatting)
async def msg_jarwas(message: Message, state: FSMContext, session: AsyncSession):
    uid = message.from_user.id
    data = await state.get_data()
    history = data.get("history", [])
    lang = data.get("lang", "ru")
    level = data.get("level")
    week = data.get("week")
    profile = data.get("profile")

    # Обновляем last_active
    participant = await ParticipantRepo(session).get(uid)
    if participant:
        participant.last_active = datetime.now(timezone.utc)
        await session.flush()

    # Проверка дневного лимита
    if not jarwas_svc.check_daily_limit(uid):
        await message.answer(
            "Брат/сестра, на сегодня лимит общения с Джарвасом исчерпан (10 сообщений в день) 🌙\n\n"
            "Возвращайся завтра — Джарвас ждёт тебя! Если срочный вопрос — напиши куратору 🤍",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Написать куратору", callback_data="contact_curator"),
            ]]),
        )
        return

    jarwas_svc.increment_daily_usage(uid)

    await message.bot.send_chat_action(message.chat.id, "typing")

    response = await jarwas_svc.ask_jarwas(
        history, message.text or "",
        level=level, week=week, user_profile=profile,
    )
    clean_text, btn_type = jarwas_svc.parse_btn_marker(response)

    history.append({"role": "user", "content": message.text})
    history.append({"role": "assistant", "content": clean_text})
    await state.update_data(history=history[-6:])

    try:
        await message.answer(
            clean_text,
            parse_mode="Markdown",
            reply_markup=kb_jarwas_actions_i18n(btn_type, lang),
        )
    except Exception:
        await message.answer(
            clean_text,
            parse_mode=None,
            reply_markup=kb_jarwas_actions_i18n(btn_type, lang),
        )


@router.callback_query(F.data == "jarwas_end")
async def cb_jarwas_end(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await call.answer()
    await state.clear()
    await call.message.answer(t(lang, "jarwas.end"))


def _build_profile(user) -> dict | None:
    if not user:
        return None
    return {
        "name": user.name,
        "occupation": user.occupation,
        "age": user.age,
        "is_female": user.is_female,
    }


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
