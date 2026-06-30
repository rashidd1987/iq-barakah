"""Диагностика уровня — квиз из 8 вопросов."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import DiagResult
from bot_v2.db.repositories import UserRepo
from bot_v2.keyboards import kb_gender, kb_diag_answer
from bot_v2.services.i18n import diag_question, diag_result, normalize_lang, t

router = Router(name="diagnostics")

QUESTIONS_COUNT = 8


class DiagStates(StatesGroup):
    gender = State()
    q0 = State()
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    q7 = State()


DIAG_STATES = [
    DiagStates.q0, DiagStates.q1, DiagStates.q2, DiagStates.q3,
    DiagStates.q4, DiagStates.q5, DiagStates.q6, DiagStates.q7,
]


@router.message(Command("diag"))
async def cmd_diag(message: Message, state: FSMContext, session: AsyncSession):
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

    if db_user and db_user.is_female is not None:
        await state.update_data(is_female=db_user.is_female, scores=[], lang=lang)
        await _ask_question(message, 0, state, lang)
    else:
        await state.set_state(DiagStates.gender)
        await state.update_data(scores=[], lang=lang)
        await message.answer(t(lang, "gender.ask"), reply_markup=kb_gender(lang))


@router.callback_query(F.data == "start_diag")
async def cb_start_diag(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await call.answer()
    await state.clear()
    user = call.from_user
    repo = UserRepo(session)
    db_user, _ = await repo.get_or_create(
        user_id=user.id,
        name=user.full_name or user.first_name or "Участник",
        username=user.username,
        language_code=normalize_lang(user.language_code),
    )
    lang = db_user.language_code or normalize_lang(user.language_code)
    if db_user.is_female is not None:
        await state.update_data(is_female=db_user.is_female, scores=[], lang=lang)
        await _ask_question(call.message, 0, state, lang)
    else:
        await state.set_state(DiagStates.gender)
        await state.update_data(scores=[], lang=lang)
        await call.message.answer(t(lang, "gender.ask"), reply_markup=kb_gender(lang))


@router.callback_query(DiagStates.gender, F.data.in_({"gender_m", "gender_f"}))
async def cb_diag_gender(call: CallbackQuery, state: FSMContext, session: AsyncSession, config=None):
    is_female = call.data == "gender_f"
    await state.update_data(is_female=is_female)
    repo = UserRepo(session)
    await repo.update(call.from_user.id, is_female=is_female)
    await call.answer()
    await call.message.edit_reply_markup()
    data = await state.get_data()
    await _ask_question(call.message, 0, state, data.get("lang"))


async def _ask_question(message: Message, q_idx: int, state: FSMContext, lang: str | None):
    text, options = diag_question(lang, q_idx)
    await state.set_state(DIAG_STATES[q_idx])
    await message.answer(text, reply_markup=kb_diag_answer(options, q_idx))


async def _handle_answer(call: CallbackQuery, state: FSMContext, session: AsyncSession, q_idx: int, score: int, config=None):
    await call.answer()
    await call.message.edit_reply_markup()
    data = await state.get_data()
    scores = data.get("scores", [])
    scores.append(score)
    await state.update_data(scores=scores)

    next_q = q_idx + 1
    if next_q < QUESTIONS_COUNT:
        await _ask_question(call.message, next_q, state, data.get("lang"))
    else:
        await _finish_diag(call, state, session, scores, config)


async def _finish_diag(call: CallbackQuery, state: FSMContext, session: AsyncSession, scores: list[int], config=None):
    import asyncio
    data = await state.get_data()
    is_female = data.get("is_female", False)
    lang = data.get("lang")
    total = sum(scores)
    result = diag_result(lang, total)

    diag = DiagResult(user_id=call.from_user.id, scores=scores, level_key=result["level_key"], pct=result["pct"])
    session.add(diag)
    await session.flush()

    repo = UserRepo(session)
    await repo.update(call.from_user.id, is_female=is_female)

    text = (
        f"{t(lang, 'diag.result_title')}\n\n"
        f"{result['emoji']} *{result['level']}* — {result['pct']}%\n\n"
        f"{result['intro']}\n\n"
        f"{t(lang, 'diag.recommended_path')}\n_{result['path']}_\n\n"
        f"{t(lang, 'diag.open_menu')}"
    )
    await call.message.answer(text, parse_mode="Markdown")
    await state.clear()

    # Авто-активация для gift_pending (форумщики и gift-ссылки)
    from bot_v2.db.repositories import SettingsRepo as _SR, ParticipantRepo as _PR
    _settings = _SR(session)
    gift_flag = await _settings.get(f"gift_pending:{call.from_user.id}")
    if gift_flag == "1":
        await _settings.set(f"gift_pending:{call.from_user.id}", "")
        p_repo = _PR(session)
        participant = await p_repo.get(call.from_user.id)
        if not participant or not participant.is_active:
            participant = await p_repo.activate(call.from_user.id, level=result["level_key"], week=1)
            await session.flush()
        await asyncio.sleep(1.5)
        level_names = {"А": "IQ Barakah Старт", "Б": "Сезон 1 — Основание", "В": "Сезон 2 — Строительство"}
        level_name = level_names.get(result["level_key"], "IQ Barakah")
        await call.bot.send_message(
            call.from_user.id,
            f"🌱 *Отлично! По результатам диагностики открываю тебе {level_name}.*\n\n"
            "Шаг 1 — Ният (намерение). Читай, делай, возвращайся. 🌿",
            parse_mode="Markdown",
        )
        try:
            from bot_v2.handlers.program import send_weekly_lesson
            await send_weekly_lesson(call.bot, call.from_user.id, participant, session, config)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("gift diag lesson: %s", e)


# Динамически регистрируем хендлеры для каждого вопроса
for _i in range(QUESTIONS_COUNT):
    def _make_handler(idx: int):
        async def _handler(call: CallbackQuery, state: FSMContext, session: AsyncSession):
            _, q_str, score_str = call.data.split(":")
            await _handle_answer(call, state, session, idx, int(score_str))
        return _handler

    router.callback_query.register(
        _make_handler(_i),
        DIAG_STATES[_i],
        F.data.startswith(f"dq:{_i}:"),
    )
