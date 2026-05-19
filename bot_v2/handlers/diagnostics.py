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
from bot_v2.services.program import get_result, QUESTIONS

router = Router(name="diagnostics")

QUESTIONS_LIST = [
    {"text": "1️⃣ Встаёшь на Фаджр?", "options": [
        ("😔 Никогда", 0), ("🔄 Иногда", 1), ("✅ Регулярно", 2), ("⭐️ Всегда + тахаджуд", 3)]},
    {"text": "2️⃣ Читаешь утренние азкары?", "options": [
        ("❌ Не читаю", 0), ("🔄 Иногда помню", 1), ("📖 Не каждый день", 2), ("✅ Каждый день", 3)]},
    {"text": "3️⃣ Планируешь свой день?", "options": [
        ("🌊 Живу как идёт", 0), ("💭 Список в голове", 1), ("📝 Пишу иногда", 2), ("⭐️ Фаджр-лист каждый день", 3)]},
    {"text": "4️⃣ Делаешь мухасабу вечером?", "options": [
        ("❓ Что это?", 0), ("💭 Иногда", 1), ("🔄 Пробовал — бросил", 2), ("✅ Каждый вечер", 3)]},
    {"text": "5️⃣ Как у тебя с телефоном утром?", "options": [
        ("📱 Телефон управляет мной", 0), ("🔄 Пытаюсь ограничить", 1),
        ("⚖️ Есть правила — срываюсь", 2), ("✅ Контролирую", 3)]},
    {"text": "6️⃣ Читаешь Коран?", "options": [
        ("❌ Не читаю", 0), ("🌙 По праздникам", 1), ("📖 Иногда в неделю", 2), ("✅ Каждый день", 3)]},
    {"text": "7️⃣ Как твой бизнес или работа?", "options": [
        ("🌀 Полный хаос", 0), ("⚙️ Без системы", 1),
        ("📊 Система есть — нет баракта", 2), ("✨ Ищу смысл", 3)]},
    {"text": "8️⃣ Как дела в твоей семье?", "options": [
        ("🏃 Почти не бываю дома", 0), ("📱 Бываю — но в телефоне", 1),
        ("❤️ Уделяю — хочу больше", 2), ("🏠 Семья — моя крепость", 3)]},
]


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
    db_user = await repo.get(user.id)

    if db_user and db_user.is_female is not None:
        await state.update_data(is_female=db_user.is_female, scores=[])
        await _ask_question(message, 0, state)
    else:
        await state.set_state(DiagStates.gender)
        await state.update_data(scores=[])
        await message.answer("Прежде чем начать — ты:", reply_markup=kb_gender())


@router.callback_query(DiagStates.gender, F.data.in_({"gender_m", "gender_f"}))
async def cb_diag_gender(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    is_female = call.data == "gender_f"
    await state.update_data(is_female=is_female)
    repo = UserRepo(session)
    await repo.update(call.from_user.id, is_female=is_female)
    await call.answer()
    await call.message.edit_reply_markup()
    await _ask_question(call.message, 0, state)


async def _ask_question(message: Message, q_idx: int, state: FSMContext):
    q = QUESTIONS_LIST[q_idx]
    await state.set_state(DIAG_STATES[q_idx])
    await message.answer(q["text"], reply_markup=kb_diag_answer(q["options"], q_idx))


async def _handle_answer(call: CallbackQuery, state: FSMContext, session: AsyncSession, q_idx: int, score: int):
    await call.answer()
    await call.message.edit_reply_markup()
    data = await state.get_data()
    scores = data.get("scores", [])
    scores.append(score)
    await state.update_data(scores=scores)

    next_q = q_idx + 1
    if next_q < len(QUESTIONS_LIST):
        await _ask_question(call.message, next_q, state)
    else:
        await _finish_diag(call, state, session, scores)


async def _finish_diag(call: CallbackQuery, state: FSMContext, session: AsyncSession, scores: list[int]):
    data = await state.get_data()
    is_female = data.get("is_female", False)
    total = sum(scores)
    result = get_result(total, is_female)

    diag = DiagResult(user_id=call.from_user.id, scores=scores, level_key=result["level_key"], pct=result["pct"])
    session.add(diag)
    await session.flush()

    repo = UserRepo(session)
    await repo.update(call.from_user.id, is_female=is_female)

    text = (
        f"🎯 *Результат диагностики*\n\n"
        f"{result['emoji']} *{result['level']}* — {result['pct']}%\n\n"
        f"{result['intro']}\n\n"
        f"📍 Рекомендованный путь:\n_{result['path']}_\n\n"
        "Напиши /start чтобы открыть меню. 🌿"
    )
    await call.message.answer(text, parse_mode="Markdown")
    await state.clear()


# Динамически регистрируем хендлеры для каждого вопроса
for _i in range(len(QUESTIONS_LIST)):
    def _make_handler(idx: int):
        async def _handler(call: CallbackQuery, state: FSMContext, session: AsyncSession):
            _, q_str, score_str = call.data.split(":")
            if int(q_str) == idx:
                await _handle_answer(call, state, session, idx, int(score_str))
        return _handler

    router.callback_query(
        DIAG_STATES[_i], F.data.startswith(f"dq:{_i}:")
    ).register(_make_handler(_i))
