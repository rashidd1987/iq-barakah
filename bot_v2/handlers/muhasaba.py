"""Вечерняя мухасаба — 3 вопроса честности перед собой.

Это ЕДИНСТВЕННЫЙ FSM для вечернего разбора.
EveningStates в start.py — удалить (см. комментарий в конце файла).
"""
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.repositories import MuhasabaRepo, UserRepo, SettingsRepo
from bot_v2.services.jarwas import ask_jarwas_muhasaba

router = Router(name="muhasaba")

MUH_QUESTIONS = [
    (
        "🌿 *Вопрос 1 из 3*\n\n"
        "«Что сегодня получилось — даже самое маленькое?»\n\n"
        "_Аллах видит каждое усилие, даже если его не видит никто._"
    ),
    (
        "💭 *Вопрос 2 из 3*\n\n"
        "«Что далось тяжело — и почему?»\n\n"
        "_Честность с собой — это уже часть поклонения. Не суди себя, просто замечай._"
    ),
    (
        "🌙 *Вопрос 3 из 3*\n\n"
        "«Что хочу сделать иначе завтра?»\n\n"
        "_Одно маленькое намерение — уже шаг вперёд. БисмиЛлях._"
    ),
]

INTRO = (
    "🌙 *Вечерний самоотчёт (мухасаба)*\n"
    "_Три вопроса честности перед собой_\n\n"
    "«Считайте себя прежде, чем будете посчитаны» — Умар ибн аль-Хаттаб (р.а.)\n\n"
    "Это займёт 2 минуты. Ответы сохранятся только у тебя.\n\n"
)

# Поздравления за стрик
STREAK_MILESTONES = {
    7:  "Хвала Аллаху! Неделя подряд 🔥\nТы держишь систему 7 дней.",
    14: "Две недели подряд 💪\nСистема начинает работать на тебя, а не ты на неё.",
    30: "30 дней 🌟\nЭто уже не попытка — это привычка. Ты изменился.",
    40: "40 дней 🤲\nВ нашей традиции 40 дней — точка трансформации. Ты прошёл её.",
}


class MuhasabaStates(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()


@router.message(Command("muhasaba"))
async def cmd_muhasaba(message: Message, state: FSMContext):
    await state.set_state(MuhasabaStates.q1)
    await state.update_data(answers=[])
    await message.answer(
        INTRO + MUH_QUESTIONS[0],
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.callback_query(F.data == "start_muhasaba")
async def cb_start_muhasaba(call: CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(MuhasabaStates.q1)
    await state.update_data(answers=[])
    await call.message.answer(
        INTRO + MUH_QUESTIONS[0],
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(MuhasabaStates.q1)
async def muh_q1(message: Message, state: FSMContext):
    await state.update_data(answers=[message.text.strip()])
    await state.set_state(MuhasabaStates.q2)
    await message.answer(MUH_QUESTIONS[1], parse_mode="Markdown")


@router.message(MuhasabaStates.q2)
async def muh_q2(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", []) + [message.text.strip()]
    await state.update_data(answers=answers)
    await state.set_state(MuhasabaStates.q3)
    await message.answer(MUH_QUESTIONS[2], parse_mode="Markdown")


@router.message(MuhasabaStates.q3)
async def muh_q3(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    answers = data.get("answers", [])
    q1 = answers[0] if len(answers) > 0 else "—"
    q2 = answers[1] if len(answers) > 1 else "—"
    q3 = message.text.strip()

    await state.clear()
    uid = message.from_user.id

    # Сохраняем в БД
    await MuhasabaRepo(session).save(
        user_id=uid,
        answers=[
            {"q": "Что получилось?", "a": q1},
            {"q": "Что далось тяжело?", "a": q2},
            {"q": "Что сделаю иначе завтра?", "a": q3},
        ],
    )

    # ── Стрик ────────────────────────────────────────────
    streak_repo = SettingsRepo(session)
    streak_val = await streak_repo.get(f"streak:{uid}", "0")
    try:
        streak = int(streak_val) + 1
    except ValueError:
        streak = 1
    await streak_repo.set(f"streak:{uid}", str(streak))

    # Получаем имя ДО commit (пока сессия активна)
    user = await UserRepo(session).get(uid)
    name = (user.name or "").split()[0] if user else ""
    barat = f", {name}" if name else ""

    await session.commit()

    # AI-рефлексия от Джарваса
    await message.bot.send_chat_action(message.chat.id, "typing")
    reflection = await ask_jarwas_muhasaba(q1, q2, q3)

    # Итоговое сообщение с благодарностью
    final_text = (
        f"Баракаллаху фик (да благословит тебя Аллах) 🌿\n\n"
        f"Ты завершил день честно{barat}.\n\n"
        f"✅ Вечерний самоотчёт записан\n\n{reflection}\n\n"
        f"Спокойной ночи 🌙\n\n"
        f"/mymuhasaba — перечитать свои записи"
    )
    try:
        await message.answer(final_text, parse_mode="Markdown")
    except Exception:
        # Fallback без Markdown если AI вернул спецсимволы
        await message.answer(final_text, parse_mode=None)

    # Стрик-поздравление
    streak_msg = STREAK_MILESTONES.get(streak)
    if streak_msg:
        await message.answer(streak_msg)


@router.callback_query(F.data == "silence_back")
async def cb_silence_back(call: CallbackQuery):
    await call.answer("Рады что ты здесь 🌿")
    await call.message.edit_text(
        "🌿 *Рады что ты вернулся!*\n\n"
        "Продолжай в своём темпе — Аллах видит каждое усилие.\n\n"
        "Отправь /jarwas чтобы поговорить с Джарвасом. 📖",
        parse_mode="Markdown",
    )


@router.message(Command("mymuhasaba"))
async def cmd_mymuhasaba(message: Message, session: AsyncSession):
    logs = await MuhasabaRepo(session).recent(message.from_user.id, limit=5)
    if not logs:
        await message.answer(
            "📓 У тебя пока нет записей вечернего самоотчёта.\n\n"
            "Нажми /muhasaba (вечерний самоотчёт) и ответь на три вопроса.",
            parse_mode="Markdown",
        )
        return

    text = f"📓 *Твои записи вечернего самоотчёта* (последние {len(logs)})\n\n"
    for log in logs:
        dt = log.created_at
        date_str = dt.strftime("%d.%m.%Y") if dt else "—"
        time_str = dt.strftime("%H:%M") if dt else ""
        answers = log.answers or []
        a1 = next((a["a"] for a in answers if "получилось" in a.get("q", "").lower()), "—")
        a2 = next((a["a"] for a in answers if "тяжело" in a.get("q", "").lower()), "—")
        a3 = next((a["a"] for a in answers if "иначе" in a.get("q", "").lower()), "—")
        text += (
            f"📅 *{date_str}* в {time_str} МСК\n"
            f"🌿 {a1}\n"
            f"💭 {a2}\n"
            f"🌙 {a3}\n"
            f"{'─' * 22}\n"
        )
    await message.answer(text, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────
# ЧТО УДАЛИТЬ ИЗ start.py
# ─────────────────────────────────────────────────────────
# 1. class EveningStates(StatesGroup): q1, q2, q3
# 2. @router.message(EveningStates.q1) async def evening_q1(...)
# 3. @router.message(EveningStates.q2) async def evening_q2(...)
# 4. @router.message(EveningStates.q3) async def evening_q3(...)
#
# ЧТО ИЗМЕНИТЬ В start.py
# msg_muhasaba / cb "start_evening" → заменить тело на:
#
# async def msg_muhasaba(update, state: FSMContext, session: AsyncSession):
#     if isinstance(update, Message):
#         await state.clear()
#         from aiogram.types import ReplyKeyboardRemove
#         await state.set_state(MuhasabaStates.q1)
#         await state.update_data(answers=[])
#         from bot_v2.handlers.muhasaba import INTRO, MUH_QUESTIONS
#         await update.answer(
#             INTRO + MUH_QUESTIONS[0],
#             parse_mode="Markdown",
#             reply_markup=ReplyKeyboardRemove(),
#         )
#     else:
#         from bot_v2.handlers.muhasaba import cb_start_muhasaba
#         await cb_start_muhasaba(update, state)
# ─────────────────────────────────────────────────────────
