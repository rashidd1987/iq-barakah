"""Кораблик IQ Barakah — 7-вопросная диагностика жизненных отсеков."""
import asyncio
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.config import Config
from bot_v2.db.repositories import UserRepo

logger = logging.getLogger(__name__)

router = Router(name="korablik")

OWNER_USERNAME = "rasid_iqbarakah"

QUESTIONS = [
    {
        "title": "Вера и намерение",
        "text": "Отсек 1 из 7 ⚓\n\nЕсть ли у тебя ощущение, что живёшь\nс намерением — знаешь зачем и ради чего?",
        "opts": [
            ("😶 Нет, живу как идёт", 0),
            ("🌧 Иногда чувствую — потом теряю", 1),
            ("🌤 В целом есть внутренняя опора", 2),
            ("☀️ Да, каждый день осознанно", 3),
        ],
    },
    {
        "title": "Время и утро",
        "text": "Отсек 2 из 7 ⚓\n\nКак начинается твой день?",
        "opts": [
            ("📱 Сразу в телефон — и так до вечера", 0),
            ("🌀 Встаю, но без цели и ритма", 1),
            ("☀️ Есть что-то стабильное по утрам", 2),
            ("🌟 Утро — якорь всего моего дня", 3),
        ],
    },
    {
        "title": "Цели и движение",
        "text": "Отсек 3 из 7 ⚓\n\nТы движешься к тому, чего хочешь?",
        "opts": [
            ("😔 Цели есть — движения нет", 0),
            ("🔄 Стартую и быстро останавливаюсь", 1),
            ("📈 Двигаюсь, но нестабильно", 2),
            ("🎯 Есть курс — и я его держу", 3),
        ],
    },
    {
        "title": "Семья и отношения",
        "text": "Отсек 4 из 7 ⚓\n\nКак ты присутствуешь в жизни близких?",
        "opts": [
            ("🏃 Постоянно в хаосе — не до них", 0),
            ("📱 Я рядом, но мыслями не здесь", 1),
            ("❤️ Стараюсь быть лучше", 2),
            ("🏠 Есть тепло, порядок и присутствие", 3),
        ],
    },
    {
        "title": "Деньги и дело",
        "text": "Отсек 5 из 7 ⚓\n\nКак обстоят дела с работой и финансами?",
        "opts": [
            ("😰 Постоянный стресс и нехватка", 0),
            ("⚖️ Хватает, но нет роста", 1),
            ("📊 Есть движение вперёд", 2),
            ("💎 Чувствую баракат в своём деле", 3),
        ],
    },
    {
        "title": "Здоровье и энергия",
        "text": "Отсек 6 из 7 ⚓\n\nКак у тебя с энергией и телом?",
        "opts": [
            ("😴 Хроническая усталость", 0),
            ("⚡ Бывают хорошие дни", 1),
            ("💪 В целом держусь", 2),
            ("🌿 Слежу за телом — это мой инструмент", 3),
        ],
    },
    {
        "title": "Внутренний мир и смысл",
        "text": "Отсек 7 из 7 ⚓\n\nЕсть ли у тебя ощущение смысла и покоя?",
        "opts": [
            ("😶 Пустота — зачем всё это", 0),
            ("🌧 Иногда теряюсь", 1),
            ("🌤 В целом есть внутренняя опора", 2),
            ("☀️ Живу с ощущением пути и цели", 3),
        ],
    },
]

SECTION_BREAKDOWN = {
    "Вера и намерение": {
        0: ("🔴", "Ты живёшь скорее по инерции, чем по намерению.\nЭто не слабость — просто никто не показал как иначе.", "Начать день с одного осознанного намерения"),
        1: ("🟡", "Намерение иногда есть — но держится недолго.\nВажно создать якорь, который будет возвращать.", "Записывать ният каждое утро — одним предложением"),
        2: ("🟢", "Есть внутренняя опора. Теперь важно углубить её и сделать ежедневной практикой.", "Углубить через программу"),
        3: ("✨", "Хвала Аллаху — ты живёшь осознанно. Это основа всего.", None),
    },
    "Время и утро": {
        0: ("🔴", "Утро уходит в телефон — и день уже потерян.\nОдин якорь с утра меняет всё.", "Одно действие до телефона — каждое утро"),
        1: ("🟡", "Ты встаёшь, но без курса. День управляет тобой, а не ты днём.", "Определить одно утреннее действие и делать его 7 дней"),
        2: ("🟢", "Есть ритм по утрам. Нужно сделать его более осознанным.", "Добавить намерение к утреннему ритуалу"),
        3: ("✨", "Утро — якорь. Это уже меняет качество всего дня.", None),
    },
    "Цели и движение": {
        0: ("🔴", "Цели есть — системы нет.\nБез системы даже сильный человек топчется на месте.", "Один маленький шаг в день — не список, а один шаг"),
        1: ("🟡", "Ты стартуешь — но не держишь. Нужна не мотивация, а ритм.", "Выбрать одну цель и делать шаг каждый день 2 недели"),
        2: ("🟢", "Есть движение, но нестабильно. Нужна система удержания.", "Добавить вечерний отчёт: сделал шаг или нет"),
        3: ("✨", "Держишь курс — это редкость. Теперь важна глубина.", None),
    },
    "Семья и отношения": {
        0: ("🔴", "Хаос вытесняет присутствие.\nБлизкие чувствуют твоё отсутствие, даже когда ты рядом.", "15 минут без телефона с близкими — каждый день"),
        1: ("🟡", "Ты рядом — но не полностью здесь.\nПрисутствие важнее времени.", "Один разговор в день — глаза в глаза, без экрана"),
        2: ("🟢", "Ты стараешься быть лучше. Нужно перейти от намерения к системе.", "Семейный ритуал — одно действие каждую неделю"),
        3: ("✨", "Есть тепло и порядок. Это фундамент.", None),
    },
    "Деньги и дело": {
        0: ("🔴", "Стресс вокруг денег забирает энергию на всё остальное.\nЭто замкнутый круг — и из него есть выход.", "Прояснить: где утекает, где можно добавить — один пункт"),
        1: ("🟡", "Хватает, но нет роста. Дело работает, но без стратегии.", "Один шаг в неделю по развитию дела"),
        2: ("🟢", "Движение есть. Нужно добавить систему и намерение.", "Соединить дело с миссией — зачем это, кроме денег"),
        3: ("✨", "Баракат в деле — это видно. Теперь масштаб и служение.", None),
    },
    "Здоровье и энергия": {
        0: ("🔴", "Хроническая усталость — это сигнал, не норма.\nТело говорит: что-то нужно изменить.", "Одно действие для тела каждый день — даже 10 минут"),
        1: ("🟡", "Хорошие дни есть — но нет стабильности.\nЭнергия нужна для всего остального.", "Сон и подъём в одно время — 5 дней подряд"),
        2: ("🟢", "В целом держишься. Добавь осознанность к заботе о теле.", "Отслеживать энергию: что даёт, что забирает"),
        3: ("✨", "Тело — инструмент, и ты за ним следишь. Это редкость.", None),
    },
    "Внутренний мир и смысл": {
        0: ("🔴", "Ощущение пустоты — это не конец.\nЭто сигнал: что-то важное ждёт, чтобы его открыли.", "Один разговор с собой: чего я на самом деле хочу"),
        1: ("🟡", "Иногда теряешься — и это нормально.\nВажно знать, как возвращаться.", "Вечерний вопрос: за что я благодарен сегодня"),
        2: ("🟢", "Опора есть. Нужно сделать её более осознанной и глубокой.", "Найти то, что возвращает к смыслу — и делать это регулярно"),
        3: ("✨", "Живёшь с ощущением пути. Это самое ценное.", None),
    },
}


class KorablikStates(StatesGroup):
    question = State()
    waiting_objection = State()


def _question_kb(q_index: int) -> InlineKeyboardMarkup:
    opts = QUESTIONS[q_index]["opts"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"kq_{q_index}_{score}")]
        for text, score in opts
    ])


def _kb(*buttons) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d)] for t, d in buttons
    ])


def _build_breakdown(scores: list) -> str:
    lines = []
    for q, score in zip(QUESTIONS, scores):
        title = q["title"]
        icon, desc, step = SECTION_BREAKDOWN[title][score]
        if score == 3:
            lines.append(f"{icon} *{title}* — Хвала Аллаху — здесь уже всё хорошо.")
        else:
            lines.append(f"{icon} *{title}*")
            lines.append(desc)
            if step:
                lines.append(f"→ _{step}_")
        lines.append("")
    return "\n".join(lines)


def _get_level(total: int) -> str:
    if total <= 7:
        return "пробуждение"
    elif total <= 14:
        return "практика"
    else:
        return "баракат"


def _build_result(scores: list) -> tuple:
    total = sum(scores)
    level = _get_level(total)
    breakdown = _build_breakdown(scores)

    if level == "пробуждение":
        footer = (
            "━━━━━━━━━━━━━━━\n\n"
            "*Что я рекомендую:*\n\n"
            "Начни с IQ Barakah Старт — 6 недель.\n"
            "Это конструктор дня: утро, намерение, ритм.\n\n"
            "Первый сдвиг — уже в первую неделю.\n"
            "Без перегруза. Без давления на себя."
        )
        markup = _kb(
            ("🌱 Хочу начать ВАКТ", "kb_want_vakt"),
            ("📖 Расскажи подробнее", "kb_about_vakt"),
            ("🔁 Пройти снова", "kb_restart"),
        )
    elif level == "практика":
        footer = (
            "━━━━━━━━━━━━━━━\n\n"
            "*Что я рекомендую:*\n\n"
            "Шаг 1 — IQ Barakah Старт, чтобы закрыть пробоины в ритме дня.\n"
            "Шаг 2 — IQ Barakah (3 сезона), чтобы собрать всё в систему.\n\n"
            "Тебе нужна не мотивация — а среда и постоянство."
        )
        markup = _kb(
            ("🏆 Хочу в IQ Barakah", "kb_want_iq"),
            ("🔍 Что такое IQ Barakah", "kb_about_iq"),
            ("🔁 Пройти снова", "kb_restart"),
        )
    else:
        footer = (
            "━━━━━━━━━━━━━━━\n\n"
            "*Что я рекомендую:*\n\n"
            "Ты не ищешь мотивацию — ты ищешь глубину.\n"
            "Следующий шаг — среда в которой растут вместе.\n\n"
            "→ IQ Barakah — сезоны и Поток\n"
            "→ Или личная работа с наставником (Лидер Уммы)"
        )
        markup = _kb(
            ("👥 Хочу в Поток", "kb_want_jamat"),
            ("👤 Поговорить с наставником", "kb_want_leader"),
            ("🔁 Пройти снова", "kb_restart"),
        )

    text = f"Джазакаллаху хайран (да воздаст тебе Аллах благом) за честность 🙏\n\nВот твоя картина:\n\n{breakdown}{footer}"
    return text, markup, level, total


# ── Старт кораблика ──────────────────────────────────────

async def _launch_korablik(call: CallbackQuery, state: FSMContext):
    """Общий запуск Кораблика — используется из нескольких callback'ов."""
    await call.answer()
    await state.update_data(k_scores=[], k_current=0)
    await state.set_state(KorablikStates.question)
    await call.message.answer(QUESTIONS[0]["text"], reply_markup=_question_kb(0))


@router.callback_query(F.data == "korablik_start")
async def cb_korablik_start(call: CallbackQuery, state: FSMContext):
    await _launch_korablik(call, state)


@router.callback_query(F.data == "start_diag")
async def cb_start_diag_korablik(call: CallbackQuery, state: FSMContext):
    """Перехватываем старую кнопку «Диагностика» → запускаем Кораблик."""
    await _launch_korablik(call, state)


# ── Ответы ───────────────────────────────────────────────

@router.callback_query(KorablikStates.question, F.data.startswith("kq_"))
async def cb_korablik_answer(call: CallbackQuery, state: FSMContext, session: AsyncSession, config: Config):
    await call.answer()
    _, q_idx_str, score_str = call.data.split("_")
    q_idx, score = int(q_idx_str), int(score_str)

    data = await state.get_data()
    scores = data.get("k_scores", [])
    if len(scores) <= q_idx:
        scores.append(score)
    else:
        scores[q_idx] = score

    next_q = q_idx + 1
    if next_q < len(QUESTIONS):
        await state.update_data(k_scores=scores, k_current=next_q)
        await call.message.answer(QUESTIONS[next_q]["text"], reply_markup=_question_kb(next_q))
    else:
        await state.clear()
        text, markup, level, total = _build_result(scores)
        await call.message.answer(text, parse_mode="Markdown", reply_markup=markup)

        user = await UserRepo(session).get(call.from_user.id)
        name = user.name if user else call.from_user.full_name
        uid = call.from_user.id

        # Если участник форума — активируем сразу без кнопки
        from sqlalchemy import select as _sa_select
        from bot_v2.db.models import Payment
        forum_pay = await session.scalar(
            _sa_select(Payment).where(
                Payment.user_id == uid,
                Payment.tariff_id == "forum_27_06",
                Payment.status == "paid",
            )
        )
        if forum_pay:
            from bot_v2.db.repositories import ParticipantRepo as _PR
            from bot_v2.handlers.program import send_weekly_lesson
            p_repo = _PR(session)
            participant = await p_repo.get(uid)
            if not participant or not participant.is_active:
                participant = await p_repo.activate(uid, level="А", week=1)
                await session.flush()
            await asyncio.sleep(1.5)
            await call.bot.send_message(
                uid,
                "🌱 *Диагностика завершена! Открываю первый урок IQ Barakah Старт.*\n\n"
                "Шаг 1 — Ният (намерение). Читай, делай, возвращайся. 🌿",
                parse_mode="Markdown",
            )
            try:
                await send_weekly_lesson(call.bot, uid, participant, session, config)
            except Exception as e:
                logger.warning("forum korablik lesson: %s", e)
            return

        # Бесплатный gift доступ — активируем сразу после диагностики
        from bot_v2.db.repositories import SettingsRepo as _SR2
        _gift_repo = _SR2(session)
        gift_flag = await _gift_repo.get(f"gift_pending:{uid}")
        if gift_flag == "1":
            await _gift_repo.set(f"gift_pending:{uid}", "")  # сбрасываем флаг
            from bot_v2.db.repositories import ParticipantRepo as _PR2
            from bot_v2.handlers.program import send_weekly_lesson
            p_repo2 = _PR2(session)
            participant = await p_repo2.get(uid)
            if not participant or not participant.is_active:
                participant = await p_repo2.activate(uid, level="А", week=1)
                await session.flush()
            await asyncio.sleep(1.5)
            await call.bot.send_message(
                uid,
                "🌱 *Диагностика завершена! Открываю первый шаг IQ Barakah Старт.*\n\n"
                "Шаг 1 — Ният (намерение). Читай, делай, возвращайся. 🌿",
                parse_mode="Markdown",
            )
            try:
                await send_weekly_lesson(call.bot, uid, participant, session, config)
            except Exception as e:
                logger.warning("gift korablik lesson: %s", e)
            return

        # Сохраняем время завершения кораблика для скидки 24 часа
        import time as _time
        from bot_v2.db.repositories import SettingsRepo
        repo = SettingsRepo(session)
        await repo.set(f"korablik_offer:{uid}", str(int(_time.time()) + 10800))  # 3 часа

        # Отправляем подарок — первый урок IQ Barakah Старт + скидка 24 часа
        await asyncio.sleep(1.5)
        await call.bot.send_message(
            uid,
            "🎁 *Вот твой подарок — первый шаг IQ Barakah Старт прямо сейчас.*\n\n"
            "Это бесплатно. Никакой оплаты — просто начни.\n\n"
            "И ещё одно: следующие *3 часа* IQ Barakah Старт доступен за *999 ₽* вместо 1 500 ₽.\n"
            "Это только для тебя — за то, что прошёл диагностику честно. 🌿",
            parse_mode="Markdown",
            reply_markup=_kb(
                ("🌱 Получить первый урок бесплатно", "kb_free_lesson"),
                ("💳 Купить IQ Barakah Старт за 999 ₽", "pay:vakt"),
            )
        )

        # Уведомляем куратора
        for curator_id in config.curator_ids:
            try:
                await call.bot.send_message(
                    chat_id=curator_id,
                    text=(
                        f"🚢 *Кораблик завершён*\n\n"
                        f"👤 {name} (`{uid}`)\n"
                        f"📊 Уровень: *{level.upper()}* ({total}/21)\n"
                        f"🎁 Отправлен подарок: урок + скидка 999₽"
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        # Сохраняем время для follow-up (job_check_followups проверяет каждые 30 мин)
        from bot_v2.db.repositories import SettingsRepo as _SR
        import time as _time
        _fu_repo = _SR(session)
        await _fu_repo.set(
            f"followup_at:{uid}",
            str(int(_time.time()) + 82800)  # 23 часа
        )


# ── Кнопки результата ────────────────────────────────────

@router.callback_query(F.data == "kb_free_lesson")
async def cb_free_lesson(call: CallbackQuery, session: AsyncSession, config: Config):
    """Подарок — первый шаг IQ Barakah Старт бесплатно."""
    await call.answer()
    from bot_v2.db.repositories import ParticipantRepo
    from bot_v2.handlers.program import send_weekly_lesson
    uid = call.from_user.id
    p_repo = ParticipantRepo(session)
    participant = await p_repo.get(uid)
    if not participant or not participant.is_active:
        participant = await p_repo.activate(uid, level="А", week=1)
        await session.flush()
    await call.message.answer(
        "🌱 *Отлично! Вот твой первый шаг IQ Barakah Старт.*\n\n"
        "Шаг 1 — Ният (намерение). Читай, делай шаг, возвращайся. 🌿",
        parse_mode="Markdown",
    )
    try:
        await send_weekly_lesson(call.bot, uid, participant, session, config)
    except Exception as e:
        logger.warning("free lesson send failed: %s", e)


@router.callback_query(F.data == "kb_want_vakt")
async def cb_want_vakt(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Отлично! 🚀\n\nНажми «Оплата» в меню — там выбери IQ Barakah Старт.",
        reply_markup=_kb(("💳 Перейти к оплате", "show_tariffs")),
    )

@router.callback_query(F.data == "kb_about_vakt")
async def cb_about_vakt(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "*IQ Barakah Старт* — это не курс мотивации.\n\n"
        "Это 6-недельная система возвращения ритма:\n\n"
        "• Утро: якорь дня, намерение, намаз\n"
        "• День: план вокруг намазов\n"
        "• Вечер: 3 вопроса мухасабы перед сном\n"
        "• Поддержка: Telegram-группа + якорный брат/сестра\n\n"
        "Первый сдвиг — уже в первую неделю.",
        parse_mode="Markdown",
        reply_markup=_kb(("🌱 Начать IQ Barakah Старт", "show_tariffs")),
    )

@router.callback_query(F.data == "kb_want_iq")
async def cb_want_iq(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Хвала Аллаху! 🌟\n\nIQ Barakah — 3 сезона глубокой работы.\nВыбери тариф в меню:",
        reply_markup=_kb(("🏆 Все тарифы", "show_tariffs")),
    )

@router.callback_query(F.data == "kb_about_iq")
async def cb_about_iq(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "*IQ Barakah* — 3 сезона личного развития.\n\n"
        "• Сезон 1: Основание — фундамент жизни\n"
        "• Сезон 2: Строительство — семья, дело, здоровье\n"
        "• Сезон 3: Служение — миссия и наследие\n\n"
        "Каждый сезон — группа, куратор и Поток.\nТы не идёшь один.",
        parse_mode="Markdown",
        reply_markup=_kb(("🏆 Выбрать тариф", "show_tariffs")),
    )

@router.callback_query(F.data == "kb_want_jamat")
async def cb_want_jamat(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "В одиночку сложно держать курс.\n\n"
        "В Потоке рядом люди, которые идут одним путём.\n"
        "Оставь запрос — куратор свяжется:",
        reply_markup=_kb(("👥 Запросить Поток", "pay:jamaat")),
    )

@router.callback_query(F.data == "kb_want_leader")
async def cb_want_leader(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        f"Личная работа с Рашидом — это Лидер Уммы.\n\n"
        f"Напиши ему: @{OWNER_USERNAME}\n\nИли оставь запрос:",
        reply_markup=_kb(("👑 Запросить Лидер Уммы", "pay:leader")),
    )

@router.callback_query(F.data == "kb_restart")
async def cb_restart(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(k_scores=[], k_current=0)
    await state.set_state(KorablikStates.question)
    await call.message.answer(
        "Начнём сначала 🔄\n\nОтвечай честно — это только для тебя.",
        reply_markup=_question_kb(0),
    )

# ── Follow-up ответы ─────────────────────────────────────

@router.callback_query(F.data == "kb_fu_price")
async def cb_fu_price(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Понимаю.\n\n"
        "IQ Barakah Старт — это меньше одного похода в кафе.\n"
        "А система, которая работает каждый день.\n\n"
        "Если в первую неделю не почувствуешь сдвиг —\n"
        "напиши куратору, разберёмся.",
        reply_markup=_kb(("🌱 Попробовать IQ Barakah Старт", "show_tariffs")),
    )

@router.callback_query(F.data == "kb_fu_time")
async def cb_fu_time(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Именно поэтому тебе и нужен IQ Barakah Старт 😊\n\n"
        "Не нужно выделять час в день.\n"
        "15 минут утром + 5 минут вечером.\n\n"
        "IQ Barakah Старт не добавляет задачи —\n"
        "он наводит порядок в тех, что уже есть.",
        reply_markup=_kb(("🌱 Начать IQ Barakah Старт", "show_tariffs")),
    )

@router.callback_query(F.data == "kb_fu_unsure")
async def cb_fu_unsure(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(KorablikStates.waiting_objection)
    await call.message.answer(
        "Честный ответ — хорошо.\n\n"
        "Скажи: что именно ты уже пробовал?\n"
        "Что работало, а что нет?\n\n"
        "Я не буду убеждать.\n"
        "Просто хочу понять, подойдёт ли тебе наш путь.",
    )

@router.message(KorablikStates.waiting_objection)
async def handle_objection(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    await state.clear()
    await message.answer(
        f"Спасибо за честность 🙏\n\n"
        f"Передам это куратору — он ответит лично: @{OWNER_USERNAME}",
    )
    user = await UserRepo(session).get(message.from_user.id)
    name = user.name if user else message.from_user.full_name
    for curator_id in config.curator_ids:
        try:
            await message.bot.send_message(
                curator_id,
                f"💬 *Возражение после кораблика*\n\n"
                f"👤 {name} (`{message.from_user.id}`)\n\n"
                f"{message.text}",
                parse_mode="Markdown",
            )
        except Exception:
            pass

@router.callback_query(F.data == "kb_fu_paid")
async def cb_fu_paid(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Баракаллаху фик (да благословит тебя Аллах)! 🌟\n\n"
        "Рад слышать. Добро пожаловать в путь 🌿"
    )
