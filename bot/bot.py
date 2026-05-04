#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────
#  IQ BARAKAH — TELEGRAM БОТ
#  python-telegram-bot >= 21.0
#  Запуск: python bot.py
# ─────────────────────────────────────────────────────────────────

import os
import logging
from datetime import time, datetime, timezone
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
    PicklePersistence
)

# ── CONFIG ───────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8610192874:AAGGyI8V4XktYte5Q_OH5XnU_Ukvk2SresI")
_curator_env = os.environ.get("CURATOR_ID", "140700248")
CURATOR_IDS = [int(x.strip()) for x in _curator_env.split(",") if x.strip()]

SITE        = "https://iq-barakah.ru"
MINIAPP_URL = SITE + "/miniapp.html"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── ТАРИФЫ ───────────────────────────────────────────────────────
TARIFFS = [
    {
        "id": "vakt",
        "name": "🌱 ВАКТ",
        "desc": "6 недель подготовки — фундамент пути",
        "price": 1500,
        "details": (
            "🌱 *ВАКТ — Подготовительная программа*\n\n"
            "📅 6 недель\n"
            "📱 Telegram-бот с уроками каждую неделю\n"
            "📖 Темы: Намерение, Фитра, Тауба, Сабр, Зикр\n"
            "🙋 Поддержка куратора\n\n"
            "💰 *1 500 ₽*\n"
            "🌿 300 ₽ → благотворительность"
        ),
    },
    {
        "id": "s1_month",
        "name": "📗 Сезон 1 (1 мес)",
        "desc": "Первый месяц IQ Barakah",
        "price": 5000,
        "details": (
            "📗 *IQ Barakah — Сезон 1 (1 месяц)*\n\n"
            "📅 8 недель · оплата за первый месяц\n"
            "👤 Личный наставник\n"
            "📱 Telegram-бот + Mini App\n"
            "📞 Пятница 14:00 — живой созвон с основателем IQ Barakah\n"
            "📖 Темы: Акыда, Намаз, Коран, Семья, Ризк, Здоровье\n\n"
            "💰 *5 000 ₽/мес*\n"
            "🌿 1 000 ₽ → благотворительность"
        ),
    },
    {
        "id": "s1_full",
        "name": "📗 Сезон 1 (полностью)",
        "desc": "Весь Сезон 1 — выгода 0 ₽",
        "price": 10000,
        "details": (
            "📗 *IQ Barakah — Сезон 1 (полный)*\n\n"
            "📅 8 недель целиком\n"
            "👤 Личный наставник\n"
            "📱 Telegram-бот + Mini App\n"
            "📞 Еженедельные созвоны с основателем IQ Barakah\n\n"
            "💰 *10 000 ₽*\n"
            "🌿 2 000 ₽ → благотворительность"
        ),
    },
    {
        "id": "s3_full",
        "name": "🏆 3 сезона (полный курс)",
        "desc": "24 недели — полная трансформация",
        "price": 28000,
        "details": (
            "🏆 *IQ Barakah — 3 сезона*\n\n"
            "📅 24 недели · полный курс трансформации\n"
            "👤 Личный наставник на всём пути\n"
            "📱 Telegram-бот + Mini App\n"
            "📞 Еженедельные созвоны с основателем IQ Barakah\n"
            "🎓 Сертификат выпускника\n\n"
            "💰 *28 000 ₽*\n"
            "🌿 5 600 ₽ → благотворительность"
        ),
    },
    {
        "id": "jamaat",
        "name": "👥 Джамаат",
        "desc": "Групповой формат до 12 человек",
        "price": 50000,
        "details": (
            "👥 *Джамаат*\n\n"
            "📅 Ежемесячная оплата\n"
            "👥 Группа до 12 человек\n"
            "🤝 Якорный брат/сестра\n"
            "📞 Групповые созвоны с основателем IQ Barakah\n"
            "🌍 Совместные проекты уммы\n\n"
            "💰 *50 000 ₽/мес*\n"
            "🌿 10 000 ₽ → благотворительность"
        ),
    },
    {
        "id": "leader",
        "name": "👑 Лидер Уммы",
        "desc": "Индивидуально с основателем IQ Barakah",
        "price": 250000,
        "details": (
            "👑 *Лидер Уммы*\n\n"
            "📅 Ежемесячная оплата\n"
            "🤝 Работа 1 на 1 с основателем IQ Barakah\n"
            "📞 Неограниченный доступ\n"
            "🎯 Индивидуальная программа\n"
            "🏛️ Стратегия наследия\n\n"
            "💰 *250 000 ₽/мес*\n"
            "🌿 50 000 ₽ → благотворительность"
        ),
    },
]

# ── ПРОГРАММА ПО УРОВНЯМ ─────────────────────────────────────────
# Структура: PROGRAM[level][week_index] = {"title": ..., "text": ..., "tasks": [...]}
PROGRAM = {
    # ── УРОВЕНЬ А: ВАКТ (6 недель) ───────────────────────────────
    "А": [
        {
            "title": "Неделя 1 · Намерение (Ниет)",
            "text": (
                "🌱 *Всё начинается с ниета.*\n\n"
                "Пророк ﷺ сказал: «Поистине, дела оцениваются по намерениям».\n\n"
                "Эта неделя — о том, зачем ты вообще здесь. "
                "Не «что делать», а *почему*. Когда есть ясное намерение — "
                "Аллах вкладывает баракат в каждое действие."
            ),
            "tasks": [
                "📝 Напиши своё намерение на эту программу — 3 предложения",
                "🌅 Каждое утро произноси его вслух перед первым действием дня",
                "🌙 Вечером запиши: что сделал сегодня с ниетом ради Аллаха?",
            ],
        },
        {
            "title": "Неделя 2 · Фитра — твоя природа",
            "text": (
                "🌿 *Ты создан правильным. Фитра не сломана — она просто засыпана.*\n\n"
                "Аллах вложил в тебя стремление к добру, к истине, к смыслу. "
                "Эта неделя — убрать всё лишнее и вернуться к себе настоящему."
            ),
            "tasks": [
                "🔕 Первые 10 минут после пробуждения — без телефона",
                "🤲 Произнеси «Альхамдулиллях» прежде чем взять телефон",
                "📓 Запиши 3 вещи, которые дают тебе ощущение правильности и смысла",
            ],
        },
        {
            "title": "Неделя 3 · Тауба — разворот",
            "text": (
                "🔄 *Тауба — это не слабость. Это сила.*\n\n"
                "«Аллах любит кающихся» (Аль-Бакара, 222). "
                "Каждый раз, когда ты возвращаешься — ты ближе к Аллаху, чем был до ошибки. "
                "Эта неделя — о честности с собой и обнулении."
            ),
            "tasks": [
                "🤲 Произноси «Астагфируллах» 100 раз каждый день",
                "✍️ Напиши письмо себе: что хочешь оставить позади",
                "🌙 Мухасаба каждый вечер: один поступок за который просишь прощения",
            ],
        },
        {
            "title": "Неделя 4 · Сабр — терпение как инструмент",
            "text": (
                "⚓ *Сабр — не пассивность. Сабр — это якорь в шторм.*\n\n"
                "«Поистине, Аллах — с терпеливыми» (Аль-Бакара, 153). "
                "Эта неделя — научиться не реагировать, а выбирать."
            ),
            "tasks": [
                "⏸️ Правило паузы: перед каждым раздражением — 3 глубоких вдоха",
                "📖 Читай по 1 странице Корана каждый день",
                "🚫 Найди одну привычку которая тебя ослабляет — не делай её 7 дней",
            ],
        },
        {
            "title": "Неделя 5 · Зикр — живая связь",
            "text": (
                "📿 *Зикр — это не ритуал. Это разговор с Аллахом.*\n\n"
                "«Поминайте Меня — Я буду помнить вас» (Аль-Бакара, 152). "
                "Эта неделя — сделать зикр частью дыхания, а не обязанностью."
            ),
            "tasks": [
                "🌅 Утренние азкары полностью — каждое утро",
                "🌇 Вечерние азкары — каждый вечер",
                "📿 «СубханАллах, АльхамдулиллЯх, АллахуАкбар» — по 33 раза после каждого намаза",
            ],
        },
        {
            "title": "Неделя 6 · Итог ВАКТ · Переход",
            "text": (
                "🎯 *МашаАллах, {name}! Ты прошёл ВАКТ.*\n\n"
                "За 6 недель ты заложил фундамент:\n"
                "✅ Ниет — есть\n"
                "✅ Фитра — очищена\n"
                "✅ Тауба — совершена\n"
                "✅ Сабр — практикуется\n"
                "✅ Зикр — живёт\n\n"
                "Теперь ты готов к IQ Barakah Сезон 1."
            ),
            "tasks": [
                "📝 Напиши итоговое письмо себе: что изменилось за 6 недель",
                "🌱 Выбери одну привычку из ВАКТ которую сохранишь навсегда",
                "🎯 Запишись на Сезон 1 — следующий шаг уже виден",
            ],
        },
    ],

    # ── УРОВЕНЬ Б: СЕЗОН 1 (8 недель) ───────────────────────────
    "Б": [
        {
            "title": "Неделя 1 · Акыда — фундамент всего",
            "text": (
                "🏛️ *Всё строится на основе. Акыда — твоя основа.*\n\n"
                "«Кто создал жизнь и смерть, чтобы испытать вас» (Аль-Мульк, 2). "
                "Эта неделя — переосмыслить зачем ты живёшь и кому служишь."
            ),
            "tasks": [
                "📖 Прочитай суру Аль-Ихляс осознанно — узнай её тафсир",
                "💭 Напиши ответ на вопрос: «Что значит быть мусульманином в 2025 году?»",
                "🌅 Фаджр — каждый день этой недели без пропусков",
            ],
        },
        {
            "title": "Неделя 2 · Намаз — столп дня",
            "text": (
                "🕌 *Намаз — не перерыв в жизни. Намаз — это и есть жизнь.*\n\n"
                "5 раз в день Аллах зовёт тебя лично. "
                "Эта неделя — сделать каждый намаз осознанным, не механическим."
            ),
            "tasks": [
                "⏰ Поставь азан-приложение — молись в первые 10 минут после азана",
                "🤲 Учи смысл суры Аль-Фатиха — читай её с пониманием",
                "📊 Отмечай каждый намаз в трекере — 5/5 цель на неделю",
            ],
        },
        {
            "title": "Неделя 3 · Коран — ежедневно",
            "text": (
                "📖 *Коран — это послание тебе лично.*\n\n"
                "«Это — Книга, в которой нет сомнения» (Аль-Бакара, 2). "
                "Эта неделя — установить ежедневную связь с Кораном, даже если это 5 аятов."
            ),
            "tasks": [
                "📖 Читай минимум 1 страницу Корана каждый день",
                "🎧 Слушай тилаву во время дороги или еды",
                "✍️ Выпиши 1 аят который задел тебя — напиши почему",
            ],
        },
        {
            "title": "Неделя 4 · Семья — моя крепость",
            "text": (
                "🏠 *Самая важная умма начинается дома.*\n\n"
                "Пророк ﷺ: «Лучший из вас тот, кто лучше к своей семье». "
                "Эта неделя — стать присутствующим, а не просто находящимся дома."
            ),
            "tasks": [
                "📵 Ужин без телефона — каждый день",
                "❤️ Скажи «Я тебя люблю» близкому человеку — вслух",
                "🤲 Сделай дуа за каждого члена семьи по имени",
            ],
        },
        {
            "title": "Неделя 5 · Ризк — баракат в деньгах",
            "text": (
                "💰 *Ризк приходит от Аллаха. Но ты должен открыть дверь.*\n\n"
                "«Аллах расширяет ризк для кого хочет» (Ар-Ра'd, 26). "
                "Эта неделя — убрать харам из источников и привлечь баракат."
            ),
            "tasks": [
                "📊 Запиши все источники дохода — есть ли сомнительные?",
                "🌿 Начни давать садака регулярно — хотя бы 1% от дохода",
                "📿 «Астагфируллах» 100 раз в день — открывает двери ризка",
            ],
        },
        {
            "title": "Неделя 6 · Здоровье — аманат тела",
            "text": (
                "💪 *Твоё тело — аманат от Аллаха. Ты за него отвечаешь.*\n\n"
                "Пророк ﷺ постился, ходил пешком, ел умеренно. "
                "Эта неделя — начать заботиться о теле как об ибадате."
            ),
            "tasks": [
                "🚶 30 минут ходьбы каждый день — можно с тилавой",
                "🥗 Убери из рациона одну вредную привычку в еде",
                "😴 Ложись спать до полуночи — сон это сунна",
            ],
        },
        {
            "title": "Неделя 7 · Нафс — управление собой",
            "text": (
                "⚖️ *Джихад с нафсом — главный джихад.*\n\n"
                "«Кто победил свой нафс — тот истинный сильный» (хадис). "
                "Эта неделя — выявить главного врага внутри и начать работу."
            ),
            "tasks": [
                "🔍 Найди свой главный триггер: что чаще всего выбивает из колеи?",
                "⏸️ Правило 5 минут: перед любым импульсивным действием — пауза",
                "📓 Веди дневник нафса: каждый вечер 1 победа над собой",
            ],
        },
        {
            "title": "Неделя 8 · Итог Сезона 1 · Ты другой",
            "text": (
                "🏆 *МашаАллах, {name}! Сезон 1 завершён.*\n\n"
                "8 недель — 8 сфер жизни трансформированы:\n"
                "✅ Акыда · ✅ Намаз · ✅ Коран · ✅ Семья\n"
                "✅ Ризк · ✅ Здоровье · ✅ Нафс · ✅ Система\n\n"
                "Ты уже не тот кем был 8 недель назад. "
                "Впереди — Сезон 2: Глубина."
            ),
            "tasks": [
                "📝 Письмо себе: сравни себя сейчас и 8 недель назад",
                "🪞 Зеркало прогресса — запиши 8 конкретных изменений",
                "🚀 Следующий шаг — Сезон 2: Нафс, Ахляк, Умма, Лидерство",
            ],
        },
    ],

    # ── УРОВЕНЬ В: СЕЗОН 1 УГЛУБЛЁННЫЙ (8 недель) ────────────────
    "В": [
        {
            "title": "Неделя 1 · Акыда — пересборка основы",
            "text": (
                "🏛️ *Ты уже практикуешь. Теперь — углубись.*\n\n"
                "Задача этой недели — не выучить акыду, а прожить её. "
                "Каждое решение этой недели пропускай через фильтр: "
                "«Это приближает меня к Аллаху или удаляет?»"
            ),
            "tasks": [
                "📖 Прочитай тафсир суры Аль-Мульк полностью",
                "✍️ Напиши свою личную миссию в 1 предложении",
                "🌅 Тахаджуд — хотя бы 2 ракаата 3 раза в эту неделю",
            ],
        },
        {
            "title": "Неделя 2 · Намаз — хушу",
            "text": (
                "🕌 *Намаз есть. Теперь — присутствие в намазе.*\n\n"
                "Хушу — это когда сердце стоит перед Аллахом, а не только тело. "
                "Эта неделя — качество, не количество."
            ),
            "tasks": [
                "🤲 Перед каждым намазом — 1 минута тишины и намерения",
                "📖 Выучи дополнительные суры для намаза с тафсиром",
                "📊 Оцени каждый намаз по 10-балльной шкале — ищи причину низких оценок",
            ],
        },
        {
            "title": "Неделя 3 · Коран — таджвид и тадаббур",
            "text": (
                "📖 *Коран читать умеешь. Теперь — слышать.*\n\n"
                "Тадаббур — размышление над аятами. "
                "«Неужели они не размышляют над Кораном?» (Ан-Ниса, 82)"
            ),
            "tasks": [
                "📖 Читай 3 страницы Корана каждый день",
                "✍️ Веди тафсир-дневник: 1 аят в день с размышлением",
                "🎧 Слушай шейха Судайса или Мишари — 20 минут в день",
            ],
        },
        {
            "title": "Неделя 4 · Семья — лидер дома",
            "text": (
                "🏠 *Ты хочешь влиять на мир — начни с семьи.*\n\n"
                "Пророк ﷺ был лучшим в семье. Его дом был крепостью уммы. "
                "Эта неделя — стать лидером своего дома."
            ),
            "tasks": [
                "🌿 Семейный халакат: 15 минут учёбы с семьёй раз в неделю",
                "❤️ Индивидуальное время с каждым членом семьи отдельно",
                "📓 Запиши 3 вещи которые хочешь передать детям как наследие",
            ],
        },
        {
            "title": "Неделя 5 · Ризк — система баракта",
            "text": (
                "💰 *Хочешь баракта? Построй систему, а не просто зарабатывай.*\n\n"
                "Эта неделя — выстроить финансовую систему по принципам ислама: "
                "садака, халяль-харам ревизия, долгосрочное планирование."
            ),
            "tasks": [
                "📊 Сделай полный аудит финансов: доходы, расходы, садака",
                "🌿 Увеличь садака до 2.5% — закят с каждого дохода",
                "🎯 Поставь 1 бизнес-цель на следующие 90 дней с ниетом",
            ],
        },
        {
            "title": "Неделя 6 · Здоровье — сунна тела",
            "text": (
                "💪 *Здоровье — это стратегия, а не вопрос силы воли.*\n\n"
                "Сунна в еде, сне, движении — это система которая работает 1400 лет. "
                "Эта неделя — внедри её."
            ),
            "tasks": [
                "🌙 Сон до 22:30 — каждый день недели",
                "🚶 45 минут ходьбы — не в спортзал, пешком с тасбихом",
                "🍽️ Ешь на 2/3 — правило Пророка ﷺ в питании",
            ],
        },
        {
            "title": "Неделя 7 · Нафс и миссия",
            "text": (
                "⚖️ *На этом уровне — нафс не враг, это инструмент.*\n\n"
                "Задача — научить нафс служить миссии. "
                "Что ты хочешь оставить после себя? Это и есть садака джария."
            ),
            "tasks": [
                "✍️ Напиши своё завещание — что ты хочешь оставить миру",
                "🎯 Сформулируй одну цель которая переживёт тебя",
                "🤝 Найди одного человека которому можешь передать знание",
            ],
        },
        {
            "title": "Неделя 8 · Итог · Готов к Сезону 2",
            "text": (
                "⭐️ *МашаАллах, {name}! Ты прошёл Сезон 1 на высшем уровне.*\n\n"
                "Система выстроена. Практика глубокая. Ты готов к Сезону 2: "
                "Нафс, Ахляк, Умма, Лидерство, Даават.\n\n"
                "Впереди — работа с сообществом и строительство наследия."
            ),
            "tasks": [
                "📝 Письмо себе через год: каким ты будешь через 12 месяцев?",
                "🌍 Найди 1 дело садака джария которое запустишь в следующие 30 дней",
                "🚀 Запишись на Сезон 2 — твой путь только набирает скорость",
            ],
        },
    ],
}

LEVEL_NAMES = {"А": "🌱 ВАКТ (6 нед)", "Б": "📗 Сезон 1 (8 нед)", "В": "⭐️ Сезон 1 углублённый (8 нед)"}
LEVEL_WEEKS = {"А": 6, "Б": 8, "В": 8}


# ── ГЛАВНОЕ МЕНЮ (кнопки снизу) ──────────────────────────────────
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🎯 Диагностика",     "📱 Личный кабинет"],
        ["📚 Программа",       "💳 Оплата"],
        ["🔔 Напоминания",     "💬 Связаться с куратором"],
        ["🌐 Сайт"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

# ── СОСТОЯНИЯ ────────────────────────────────────────────────────
(
    NAME, GENDER, OCCUPATION, AGE, SOURCE,
    Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8
) = range(13)

# ── ПРОФИЛЬНЫЕ ДАННЫЕ ────────────────────────────────────────────
OCCUPATIONS = [
    ("💼 Предприниматель",   "entrepreneur"),
    ("👔 Наёмный сотрудник", "employee"),
    ("🎓 Студент",           "student"),
    ("🧑‍💻 Самозанятый",      "freelance"),
]

SOURCES = [
    ("📍 Карты (2ГИС/Яндекс)", "maps"),
    ("📱 Соцсети",             "social"),
    ("🔍 Интернет/поиск",      "internet"),
    ("💬 Форумы/Telegram",     "forums"),
    ("👥 От знакомых",         "word_of_mouth"),
    ("📺 YouTube/Reels",       "video"),
]

# ── ДИАГНОСТИЧЕСКИЕ ВОПРОСЫ ──────────────────────────────────────
QUESTIONS = [
    {"text": "1️⃣ Встаёшь на Фаджр?", "options": [
        ("😔 Никогда", 0), ("🔄 Иногда", 1),
        ("✅ Регулярно", 2), ("⭐️ Всегда + тахаджуд", 3)]},
    {"text": "2️⃣ Читаешь утренние азкары?", "options": [
        ("❌ Не читаю", 0), ("🔄 Иногда помню", 1),
        ("📖 Не каждый день", 2), ("✅ Каждый день", 3)]},
    {"text": "3️⃣ Планируешь свой день?", "options": [
        ("🌊 Живу как идёт", 0), ("💭 Список в голове", 1),
        ("📝 Пишу иногда", 2), ("⭐️ Фаджр-лист каждый день", 3)]},
    {"text": "4️⃣ Делаешь мухасабу вечером?", "options": [
        ("❓ Что это?", 0), ("💭 Иногда", 1),
        ("🔄 Пробовал — бросил", 2), ("✅ Каждый вечер", 3)]},
    {"text": "5️⃣ Как у тебя с телефоном утром?", "options": [
        ("📱 Телефон управляет мной", 0), ("🔄 Пытаюсь ограничить", 1),
        ("⚖️ Есть правила — срываюсь", 2), ("✅ Контролирую", 3)]},
    {"text": "6️⃣ Читаешь Коран?", "options": [
        ("❌ Не читаю", 0), ("🌙 По праздникам", 1),
        ("📖 Иногда в неделю", 2), ("✅ Каждый день", 3)]},
    {"text": "7️⃣ Как твой бизнес или работа?", "options": [
        ("🌀 Полный хаос", 0), ("⚙️ Без системы", 1),
        ("📊 Система есть — нет баракта", 2), ("✨ Ищу смысл", 3)]},
    {"text": "8️⃣ Как дела в твоей семье?", "options": [
        ("🏃 Почти не бываю дома", 0), ("📱 Бываю — но в телефоне", 1),
        ("❤️ Уделяю — хочу больше", 2), ("🏠 Семья — моя крепость", 3)]},
]

# ── РЕЗУЛЬТАТЫ ───────────────────────────────────────────────────
def get_result(score: int, is_female: bool) -> dict:
    pct = round(score / (8 * 3) * 100)
    f = lambda m, w: w if is_female else m
    brat = "Сестра" if is_female else "Брат"

    if pct <= 25:
        return dict(level="Уровень А — Начинаю с нуля", level_key="А", pct=pct, emoji="🔴",
            intro=f"{brat}, это честный результат. Точка силы, не слабости. Ты узнал{f('','а')} где находишься.",
            pains=["😔 День управляется обстоятельствами — не твоими целями",
                   "📱 Телефон — первое что видишь утром. Задаёт тон всему дню",
                   "🌙 Фаджр уходит мимо. Самое баракатное время потеряно",
                   "🔄 Начинаешь «с понедельника» — срыв через 3-7 дней"],
            wheel="Иман 1/10 · Время 1/10 · Привычки 1/10 · Семья 2/10",
            rec="Это не твоя вина — это отсутствие системы.\n\nОдно слово «Альхамдулиллях» утром до телефона — уже разрыв шаблона.",
            path="ВАКТ", path_desc="6 недель · 1 500 ₽ · Уровень А",
            link=SITE, btn="🌱 Начать с ВАКТ")
    elif pct <= 50:
        return dict(level="Уровень Б — Иногда практикую", level_key="Б", pct=pct, emoji="🔵",
            intro=f"{brat}, ты уже на пути. Намаз бывает, Коран иногда. Но система не держится.",
            pains=["📉 Знаешь как надо — но не делаешь стабильно",
                   "🔁 Привычки: неделя хорошо — срыв — стыд — снова старт",
                   "⏰ Утро без системы. Нет якоря который держит день",
                   "🎯 Нет ясности зачем всё это"],
            wheel="Иман 3/10 · Время 4/10 · Привычки 3/10 · Семья 3/10",
            rec="Тебе нужна не мотивация.\nТебе нужна СИСТЕМА которая работает даже когда мотивации нет.",
            path="ВАКТ → IQ Barakah Сезон 1", path_desc="6 нед + 8 нед · Уровень Б",
            link=SITE, btn="🔵 Начать с ВАКТ")
    elif pct <= 75:
        return dict(level="Уровень В — Практикую регулярно", level_key="В", pct=pct, emoji="💚",
            intro=f"МашаАллах, {brat.lower()}! Намаз, азкары, Коран — есть. Но чувствуешь: чего-то не хватает.",
            pains=["🔍 Намаз без присутствия. Азкары без осознанности",
                   f"🏔️ Плато. Вырос{f('','ла')} — застрял{f('','а')}. Непонятно куда дальше",
                   "💰 Бизнес есть — нет ощущения баракта",
                   "❓ Миссия не сформулирована. Что оставишь после себя?"],
            wheel="Иман 6/10 · Время 6/10 · Привычки 6/10 · Миссия 4/10",
            rec="Тебе нужна система которая соединит духовность, бизнес, семью и миссию.",
            path="IQ Barakah Сезон 1 → Сезон 2", path_desc="8+8 нед · Уровень В",
            link=SITE, btn="🟢 Начать Сезон 1")
    else:
        return dict(level=f"Уровень В+ — Готов{f('','а')} к наследию", level_key="В", pct=pct, emoji="⭐️",
            intro=f"МашаАллах, {brat.lower()}! Практика есть, система есть. Готов{f('','а')} к большему.",
            pains=["🌍 Хочешь влиять на Умму — нет структуры",
                   "🔗 Достижения заканчиваются на тебе. Садака джария не запущена",
                   "👑 Ты лидер — но без сообщества с миссией",
                   "🏛️ Хочешь оставить наследие — не знаешь как начать"],
            wheel="Иман 8/10 · Время 8/10 · Привычки 8/10 · Миссия 6/10",
            rec="Следующий уровень — рост через других.\nДжамаат или личная работа с основателем IQ Barakah.",
            path="Джамаат или Лидер Уммы", path_desc="24 нед · До 12 чел / 1 на 1",
            link=SITE, btn="⭐️ Записаться в Джамаат")


# ── ПОМОЩНИКИ ПРОГРАММЫ ──────────────────────────────────────────

def get_active_users(ctx: ContextTypes.DEFAULT_TYPE) -> dict:
    return ctx.bot_data.setdefault("active_users", {})


async def send_week_lesson(bot, user_id: int, entry: dict):
    """Отправить урок недели конкретному пользователю."""
    level = entry["level"]
    week_idx = entry["week"] - 1
    lessons = PROGRAM.get(level, [])
    if week_idx >= len(lessons):
        return

    lesson = lessons[week_idx]
    name = entry.get("name", "Брат")
    title = lesson["title"]
    text = lesson["text"].replace("{name}", name.split()[0] if name else "Брат")
    tasks = "\n".join(f"  {t}" for t in lesson["tasks"])
    total = LEVEL_WEEKS[level]

    msg = (
        f"📅 *{title}*\n"
        f"_{LEVEL_NAMES[level]} · Неделя {entry['week']} из {total}_\n\n"
        f"{text}\n\n"
        f"*Задания на эту неделю:*\n{tasks}"
    )
    try:
        await bot.send_message(
            chat_id=user_id,
            text=msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📱 Открыть трекер", web_app=WebAppInfo(url=MINIAPP_URL)),
                InlineKeyboardButton("✅ Понял, иду делать", callback_data="week_ack"),
            ]])
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить урок пользователю {user_id}: {e}")


async def job_weekly_lesson(ctx: ContextTypes.DEFAULT_TYPE):
    """Запускается каждый понедельник в 9:00 — рассылает урок всем активным."""
    active = get_active_users(ctx)
    if not active:
        return
    sent = 0
    for uid_str, entry in list(active.items()):
        uid = int(uid_str)
        level = entry["level"]
        max_weeks = LEVEL_WEEKS.get(level, 8)
        if entry["week"] > max_weeks:
            continue
        await send_week_lesson(ctx.bot, uid, entry)
        entry["week"] += 1
        sent += 1
    logger.info(f"Еженедельная рассылка: отправлено {sent} уроков")
    # уведомить куратора
    for cid in CURATOR_IDS:
        try:
            await ctx.bot.send_message(
                chat_id=cid,
                text=f"📬 Еженедельная рассылка завершена. Отправлено уроков: *{sent}*",
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def cmd_activate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Только для кураторов. /activate <user_id> <уровень> [неделя]"""
    if update.effective_user.id not in CURATOR_IDS:
        await update.message.reply_text("⛔️ Команда только для кураторов.")
        return

    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "Использование: `/activate <user_id> <А/Б/В> [неделя]`\n\n"
            "Например: `/activate 123456789 Б`\n"
            "Или с недели: `/activate 123456789 В 3`",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id — должно быть число.")
        return

    level = args[1].upper()
    if level not in PROGRAM:
        await update.message.reply_text("❌ Уровень должен быть А, Б или В.")
        return

    week = 1
    if len(args) >= 3:
        try:
            week = max(1, min(int(args[2]), LEVEL_WEEKS[level]))
        except ValueError:
            pass

    active = get_active_users(ctx)
    # получить имя если есть в bot_data
    name = ctx.bot_data.get("user_names", {}).get(str(target_id), "Участник")

    active[str(target_id)] = {
        "level": level,
        "week": week,
        "name": name,
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }

    # уведомить участника
    try:
        await ctx.bot.send_message(
            chat_id=target_id,
            parse_mode="Markdown",
            text=(
                f"🎉 *Твоя программа активирована!*\n\n"
                f"📍 {LEVEL_NAMES[level]}\n"
                f"📅 Старт с недели {week}\n\n"
                f"Каждый понедельник в 9:00 ты будешь получать урок недели.\n"
                f"Используй /myprogram чтобы видеть свой прогресс.\n\n"
                f"🌿 _Баракат в каждом шаге!_"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📱 Открыть личный кабинет", web_app=WebAppInfo(url=MINIAPP_URL))
            ]])
        )
        participant_notified = "✅ Участник уведомлён"
    except Exception as e:
        participant_notified = f"⚠️ Не удалось уведомить: {e}"

    await update.message.reply_text(
        f"✅ *Активировано*\n\n"
        f"👤 ID: `{target_id}`\n"
        f"📍 Уровень: *{level}* ({LEVEL_NAMES[level]})\n"
        f"📅 Начинает с недели: *{week}*\n"
        f"{participant_notified}",
        parse_mode="Markdown"
    )


async def cmd_deactivate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Только для кураторов. /deactivate <user_id>"""
    if update.effective_user.id not in CURATOR_IDS:
        await update.message.reply_text("⛔️ Команда только для кураторов.")
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Использование: `/deactivate <user_id>`", parse_mode="Markdown")
        return
    try:
        target_id = str(int(args[0]))
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id.")
        return
    active = get_active_users(ctx)
    if target_id in active:
        del active[target_id]
        await update.message.reply_text(f"✅ Пользователь `{target_id}` деактивирован.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Пользователь `{target_id}` не найден в программе.", parse_mode="Markdown")


async def cmd_participants(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Только для кураторов. /participants — список всех активных."""
    if update.effective_user.id not in CURATOR_IDS:
        await update.message.reply_text("⛔️ Команда только для кураторов.")
        return
    active = get_active_users(ctx)
    if not active:
        await update.message.reply_text("Нет активных участников.")
        return
    lines = ["👥 *Активные участники:*\n"]
    for uid, e in active.items():
        level = e["level"]
        max_w = LEVEL_WEEKS.get(level, 8)
        lines.append(
            f"• `{uid}` — {e.get('name','?')} | "
            f"{LEVEL_NAMES[level]} | неделя {e['week']}/{max_w}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_send_now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Только для кураторов. /sendnow — отправить урок прямо сейчас (тест)."""
    if update.effective_user.id not in CURATOR_IDS:
        await update.message.reply_text("⛔️ Команда только для кураторов.")
        return
    await job_weekly_lesson(ctx)
    await update.message.reply_text("✅ Уроки отправлены вручную.")


async def cmd_myprogram(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Пользователь смотрит свой прогресс."""
    uid = str(update.effective_user.id)
    active = get_active_users(ctx)
    entry = active.get(uid)
    if not entry:
        await update.message.reply_text(
            "У тебя пока нет активной программы.\n\n"
            "Пройди диагностику и свяжись с куратором для активации 🌿",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎯 Пройти диагностику", callback_data="start_diag")
            ]])
        )
        return

    level = entry["level"]
    week = entry["week"]
    max_w = LEVEL_WEEKS.get(level, 8)
    done = week - 1
    bar = "🟩" * done + "⬜️" * (max_w - done)
    pct = round(done / max_w * 100)

    lessons = PROGRAM.get(level, [])
    next_title = lessons[week - 1]["title"] if week <= max_w and (week - 1) < len(lessons) else "Программа завершена!"

    await update.message.reply_text(
        f"📊 *Твоя программа*\n\n"
        f"📍 {LEVEL_NAMES[level]}\n"
        f"📅 Неделя *{week}* из *{max_w}*\n"
        f"Progress: {bar} {pct}%\n\n"
        f"*Следующий урок:*\n_{next_title}_\n\n"
        f"_Каждый понедельник в 9:00 приходит новый урок_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📱 Открыть трекер", web_app=WebAppInfo(url=MINIAPP_URL))
        ]])
    )


async def cb_week_ack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Нажата кнопка 'Понял, иду делать'."""
    query = update.callback_query
    await query.answer("МашаАллах! Баракат в каждом шаге 🌿", show_alert=False)


# ══════════════════════════════════════════════════════════════════
#  ЭТАП 3 — ЕЖЕДНЕВНЫЕ НАПОМИНАНИЯ
# ══════════════════════════════════════════════════════════════════

# Типы напоминаний: (ключ, эмодзи, название, время МСК)
REMINDER_TYPES = [
    ("morning",   "🌅", "Утренний азкар",  "06:00"),
    ("dhuhr",     "🕛", "Обеденный намаз", "13:30"),
    ("evening",   "🌇", "Вечерний азкар",  "20:00"),
    ("muhasaba",  "🌙", "Мухасаба",        "22:00"),
]

# UTC-время для каждого типа (МСК = UTC+3)
REMINDER_UTC = {
    "morning":  time(3,  0, tzinfo=timezone.utc),
    "dhuhr":    time(10, 30, tzinfo=timezone.utc),
    "evening":  time(17, 0, tzinfo=timezone.utc),
    "muhasaba": time(19, 0, tzinfo=timezone.utc),
}

REMINDER_TEXTS = {
    "morning": (
        "🌅 *Доброе утро!*\n\n"
        "بِسْمِ اللّٰهِ الرَّحْمٰنِ الرَّحِيْم\n\n"
        "«Мы достигли утра, и достигло утра всё владение Аллаха. "
        "Хвала Аллаху, нет бога кроме Аллаха Единого...»\n\n"
        "📿 Прочитай утренние азкары\n"
        "🕌 Совершил ли ты Фаджр?\n"
        "🌿 _Баракатного утра!_"
    ),
    "dhuhr": (
        "🕛 *Время Зухр*\n\n"
        "الصَّلَاةُ خَيْرٌ مِّنَ النَّوْمِ\n\n"
        "Намаз лучше сна.\n\n"
        "🕌 Пора совершить обеденный намаз\n"
        "📿 «СубханАллах» 33 раза после намаза\n"
        "🌿 _Аллах смотрит на тебя_"
    ),
    "evening": (
        "🌇 *Вечер — время азкаров*\n\n"
        "«Мы достигли вечера, и достигло вечера всё владение Аллаха...»\n\n"
        "📿 Прочитай вечерние азкары\n"
        "🕌 Не забудь Магриб и Иша\n"
        "📖 Хотя бы 1 страница Корана сегодня\n"
        "🌿 _Вечер с Аллахом — защита до утра_"
    ),
    "muhasaba": (
        "🌙 *Время мухасабы*\n\n"
        "«Считайте себя сами прежде чем вас посчитают» — Умар ибн аль-Хаттаб (р.а.)\n\n"
        "Ответь себе честно:\n"
        "✅ Что хорошего я сделал сегодня?\n"
        "🔄 Что я мог сделать лучше?\n"
        "🤲 За что я благодарю Аллаха?\n\n"
        "📱 Открой трекер — отметь выполненное\n"
        "🌿 _Астагфируллах — и спи с чистым сердцем_"
    ),
}


def get_reminders(ctx: ContextTypes.DEFAULT_TYPE) -> dict:
    return ctx.bot_data.setdefault("reminders", {})


def reminders_keyboard(uid: str, settings: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, emoji, name, t in REMINDER_TYPES:
        on = settings.get(key, False)
        status = "✅" if on else "⬜️"
        rows.append([InlineKeyboardButton(
            f"{status} {emoji} {name}  ({t} МСК)",
            callback_data=f"rem_toggle_{key}_{uid}"
        )])
    rows.append([InlineKeyboardButton("❌ Отключить все", callback_data=f"rem_off_all_{uid}")])
    return InlineKeyboardMarkup(rows)


async def cmd_reminders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    rems = get_reminders(ctx)
    settings = rems.get(uid, {})
    await update.message.reply_text(
        "🔔 *Ежедневные напоминания*\n\n"
        "Включи нужные — бот будет напоминать тебе каждый день.\n"
        "_Время указано по МСК (Москва, UTC+3)_",
        parse_mode="Markdown",
        reply_markup=reminders_keyboard(uid, settings)
    )


async def cb_rem_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    # format: rem_toggle_<key>_<uid>
    key = parts[2]
    uid = parts[3]

    if str(update.effective_user.id) != uid:
        return

    rems = get_reminders(ctx)
    settings = rems.setdefault(uid, {})
    settings[key] = not settings.get(key, False)

    await query.edit_message_reply_markup(
        reply_markup=reminders_keyboard(uid, settings)
    )
    if settings[key]:
        label = next(n for k, _, n, _ in REMINDER_TYPES if k == key)
        await query.answer(f"✅ {label} включён!", show_alert=False)


async def cb_rem_off_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.data.split("_")[-1]
    if str(update.effective_user.id) != uid:
        return
    rems = get_reminders(ctx)
    rems[uid] = {k: False for k, *_ in REMINDER_TYPES}
    await query.edit_message_reply_markup(
        reply_markup=reminders_keyboard(uid, rems[uid])
    )


async def _send_reminder(bot, uid: int, reminder_key: str):
    text = REMINDER_TEXTS[reminder_key]
    try:
        await bot.send_message(
            chat_id=uid,
            text=text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📱 Открыть трекер", web_app=WebAppInfo(url=MINIAPP_URL))
            ]])
        )
    except Exception as e:
        logger.warning(f"Reminder {reminder_key} → {uid}: {e}")


async def _job_reminder(ctx: ContextTypes.DEFAULT_TYPE, reminder_key: str):
    rems = get_reminders(ctx)
    count = 0
    for uid_str, settings in rems.items():
        if settings.get(reminder_key, False):
            await _send_reminder(ctx.bot, int(uid_str), reminder_key)
            count += 1
    if count:
        logger.info(f"Напоминание '{reminder_key}' отправлено: {count} чел.")


# ── УВЕДОМЛЕНИЕ КУРАТОРА ─────────────────────────────────────────
async def notify_curators(ctx, user, data: dict, result: dict):
    occ_map = {k: l for l, k in OCCUPATIONS}
    src_map  = {k: l for l, k in SOURCES}
    brat = "Сестра" if data.get("is_female") else "Брат"
    username = f"@{user.username}" if user.username else f"ID: {user.id}"
    text = (
        f"🌱 *Новый участник прошёл диагностику*\n\n"
        f"👤 *{data.get('name','—')}* ({username})\n"
        f"🔖 {brat} · {result['level']}\n"
        f"📊 Результат: *{result['pct']}%*\n"
        f"💼 {data.get('occupation','—')}\n"
        f"🎂 Возраст: {data.get('age','—')}\n"
        f"📣 Источник: {data.get('source','—')}\n\n"
        f"📍 Рекомендован путь: *{result['path']}*"
    )
    for cid in CURATOR_IDS:
        try:
            await ctx.bot.send_message(chat_id=cid, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Куратор {cid}: {e}")


# ══════════════════════════════════════════════════════════════════
#  СТАТИЧЕСКИЕ ХЭНДЛЕРЫ (кнопки меню)
# ══════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    ctx.user_data["scores"] = []
    user = update.effective_user
    # сохранить username глобально для якорных пар
    uid = str(user.id)
    ctx.bot_data.setdefault("user_usernames", {})[uid] = user.username
    name = user.first_name or "друг"
    await update.message.reply_text(
        f"✨ *Ассаляму алейкум, {name}!*\n\n"
        "Добро пожаловать в *IQ Barakah* — платформу исламского личностного роста.\n\n"
        "Используй меню ниже 👇",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )
    return ConversationHandler.END


async def cmd_diag(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Старт диагностики — из кнопки или /diag"""
    ctx.user_data.clear()
    ctx.user_data["scores"] = []
    await update.message.reply_text(
        "🎯 *Бесплатная диагностика IQ Barakah*\n\n"
        "8 вопросов — узнаешь:\n"
        "• Где ты сейчас на пути\n"
        "• Что мешает двигаться дальше\n"
        "• С чего начать именно тебе\n\n"
        "Для начала — как тебя зовут? _(Имя и фамилия)_",
        parse_mode="Markdown"
    )
    return NAME


async def cmd_miniapp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Открыть Mini App"""
    await update.message.reply_text(
        "📱 *Личный кабинет IQ Barakah*\n\n"
        "Трекер намаза и привычек, колесо баланса, карта пути и мухасаба — всё внутри.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📱 Открыть личный кабинет", web_app=WebAppInfo(url=MINIAPP_URL))
        ]])
    )


async def cmd_program(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Описание программы"""
    await update.message.reply_text(
        "📚 *Программа IQ Barakah*\n\n"
        "Путь из 30 недель · 3 сезона + подготовительный ВАКТ\n\n"
        "🌱 *ВАКТ* — 6 недель · Фундамент\n"
        "_Намерение, фитра, тауба, сабр, зикр_\n\n"
        "📗 *Сезон 1* — 8 недель · Система\n"
        "_Акыда, намаз, Коран, семья, ризк, здоровье_\n\n"
        "📘 *Сезон 2* — 8 недель · Глубина\n"
        "_Нафс, ахляк, уммет, лидерство, даават_\n\n"
        "📙 *Сезон 3* — 8 недель · Наследие\n"
        "_Трансформация, миссия, влияние, садака джария_\n\n"
        "⏰ Понедельник 9:00 — урок недели\n"
        "📞 Пятница 14:00 — живой созвон с Рашидом\n"
        "🌙 Ежедневно — азкар + мухасаба\n\n"
        "🌿 _20% с каждой оплаты → благотворительность_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎯 Пройти диагностику", callback_data="start_diag")
        ]])
    )


def tariff_keyboard(tariff_id: str) -> InlineKeyboardMarkup:
    """Кнопки под карточкой тарифа."""
    price = next(t["price"] for t in TARIFFS if t["id"] == tariff_id)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 Оплатить {price:,} ₽".replace(",", " "), callback_data=f"pay_{tariff_id}")],
        [InlineKeyboardButton("◀️ Все тарифы", callback_data="show_tariffs")],
    ])


async def cmd_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Список всех тарифов с кнопками оплаты."""
    rows = []
    for t in TARIFFS:
        rows.append([InlineKeyboardButton(
            f"{t['name']} — {t['price']:,} ₽".replace(",", " "),
            callback_data=f"tariff_{t['id']}"
        )])
    rows.append([InlineKeyboardButton("🎯 Сначала пройти диагностику", callback_data="start_diag")])

    msg = update.message if update.message else update.callback_query.message
    await msg.reply_text(
        "💳 *Выберите тариф*\n\n"
        "🌿 _20% от каждой оплаты → благотворительность_\n\n"
        "Нажмите на тариф чтобы узнать подробнее и оплатить:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )


async def cb_show_tariff(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Карточка конкретного тарифа."""
    query = update.callback_query
    await query.answer()
    tariff_id = query.data.replace("tariff_", "")
    t = next((x for x in TARIFFS if x["id"] == tariff_id), None)
    if not t:
        return
    await query.edit_message_text(
        t["details"],
        parse_mode="Markdown",
        reply_markup=tariff_keyboard(tariff_id)
    )


async def cb_show_tariffs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Вернуться к списку тарифов."""
    query = update.callback_query
    await query.answer()
    rows = []
    for t in TARIFFS:
        rows.append([InlineKeyboardButton(
            f"{t['name']} — {t['price']:,} ₽".replace(",", " "),
            callback_data=f"tariff_{t['id']}"
        )])
    rows.append([InlineKeyboardButton("🎯 Сначала пройти диагностику", callback_data="start_diag")])
    await query.edit_message_text(
        "💳 *Выберите тариф*\n\n"
        "🌿 _20% от каждой оплаты → благотворительность_\n\n"
        "Нажмите на тариф чтобы узнать подробнее и оплатить:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )


async def cb_pay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия 'Оплатить'."""
    query = update.callback_query
    await query.answer()
    tariff_id = query.data.replace("pay_", "")
    t = next((x for x in TARIFFS if x["id"] == tariff_id), None)
    if not t:
        return

    user = update.effective_user
    username = f"@{user.username}" if user.username else f"ID {user.id}"
    price_rub = f"{t['price']:,}".replace(",", " ")

    # Уведомить куратора
    for cid in CURATOR_IDS:
        try:
            await ctx.bot.send_message(
                chat_id=cid,
                parse_mode="Markdown",
                text=(
                    f"💳 *Запрос на оплату*\n\n"
                    f"👤 {user.full_name} ({username})\n"
                    f"📦 Тариф: *{t['name']}*\n"
                    f"💰 Сумма: *{price_rub} ₽*\n\n"
                    f"Свяжитесь с участником для выставления счёта."
                )
            )
        except Exception:
            pass

    await query.edit_message_text(
        f"✅ *Заявка принята!*\n\n"
        f"📦 Тариф: *{t['name']}*\n"
        f"💰 Сумма: *{price_rub} ₽*\n\n"
        f"Куратор свяжется с тобой в течение нескольких часов "
        f"и вышлет реквизиты для оплаты.\n\n"
        f"📧 info@iqbarakah.ru\n"
        f"🌿 _Баракат в каждом шаге_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Все тарифы", callback_data="show_tariffs")],
            [InlineKeyboardButton("🎯 Пройти диагностику", callback_data="start_diag")],
        ])
    )


async def cmd_prices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Цены — алиас на оплату."""
    await cmd_payment(update, ctx)


async def cmd_site(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Сайт"""
    await update.message.reply_text(
        "🌐 *Сайт IQ Barakah*\n\nВся информация, программа и запись:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Открыть iq-barakah.ru", url=SITE)
        ]])
    )


async def cmd_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Связь с куратором"""
    user = update.effective_user
    username = f"@{user.username}" if user.username else f"ID {user.id}"
    # уведомить куратора
    for cid in CURATOR_IDS:
        try:
            await ctx.bot.send_message(
                chat_id=cid,
                text=f"💬 *Запрос связи с куратором*\n\n"
                     f"👤 {user.full_name} ({username})\n"
                     f"Хочет связаться.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    await update.message.reply_text(
        "💬 *Связь с куратором*\n\n"
        "Твой запрос отправлен — куратор свяжется с тобой в течение нескольких часов.\n\n"
        "📧 info@iqbarakah.ru\n"
        "🌐 iq-barakah.ru",
        parse_mode="Markdown"
    )


# ── CALLBACK: старт диагностики из inline-кнопки ─────────────────
async def cb_start_diag(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    ctx.user_data["scores"] = []
    await query.message.reply_text(
        "🎯 *Начинаем диагностику!*\n\nКак тебя зовут? _(Имя и фамилия)_",
        parse_mode="Markdown"
    )
    return NAME


# ══════════════════════════════════════════════════════════════════
#  ДИАГНОСТИКА — ХЭНДЛЕРЫ РАЗГОВОРА
# ══════════════════════════════════════════════════════════════════

async def got_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    # игнорируем нажатия кнопок меню
    if name in ["🎯 Диагностика", "📱 Личный кабинет", "📚 Программа",
                "💰 Цены", "🌐 Сайт", "💬 Связаться с куратором"]:
        await update.message.reply_text("Введи своё имя и фамилию 🌿")
        return NAME
    if len(name) < 2:
        await update.message.reply_text("Пожалуйста, введи своё имя 🌿")
        return NAME
    ctx.user_data["name"] = name
    # сохранить имя глобально чтобы куратор видел его при /participants
    ctx.bot_data.setdefault("user_names", {})[str(update.effective_user.id)] = name
    await update.message.reply_text(
        f"Отлично, *{name.split()[0]}*! 🌿\n\nКто ты?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🧔 Я брат", callback_data="gender_m"),
            InlineKeyboardButton("🧕 Я сестра", callback_data="gender_f"),
        ]])
    )
    return GENDER


async def got_gender(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ctx.user_data["is_female"] = (query.data == "gender_f")
    await query.edit_message_text(
        "Понял 🌿\n\n*Чем ты занимаешься?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(label, callback_data=f"occ_{key}")]
            for label, key in OCCUPATIONS
        ])
    )
    return OCCUPATION


async def got_occupation(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.replace("occ_", "")
    label = next((l for l, k in OCCUPATIONS if k == key), key)
    ctx.user_data["occupation"] = label
    await query.edit_message_text(
        f"✅ {label}\n\n*Сколько тебе лет?* _(напиши цифру, например: 32)_",
        parse_mode="Markdown"
    )
    return AGE


async def got_age(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or not (10 <= int(text) <= 99):
        await update.message.reply_text("Введи возраст цифрой, например: *28*", parse_mode="Markdown")
        return AGE
    ctx.user_data["age"] = text
    await update.message.reply_text(
        "Хорошо! 🌿\n\n*Откуда ты узнал(а) о нас?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(label, callback_data=f"src_{key}")]
            for label, key in SOURCES
        ])
    )
    return SOURCE


async def got_source(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.replace("src_", "")
    label = next((l for l, k in SOURCES if k == key), key)
    ctx.user_data["source"] = label
    name_first = ctx.user_data.get("name", "").split()[0]
    brat = "сестра" if ctx.user_data.get("is_female") else "брат"
    await query.edit_message_text(
        f"Отлично, {brat} *{name_first}*! 🌿\n\n"
        "_Теперь честно посмотрим где ты сейчас._\n"
        "8 вопросов — без стыда и без давления.",
        parse_mode="Markdown"
    )
    await send_question(update, ctx, 0)
    return Q1


async def send_question(update: Update, ctx: ContextTypes.DEFAULT_TYPE, q_idx: int):
    q = QUESTIONS[q_idx]
    keyboard = [[InlineKeyboardButton(text, callback_data=f"ans_{q_idx}_{score}")]
                for text, score in q["options"]]
    await ctx.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"*{q['text']}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def answer_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    q_idx, score = int(parts[1]), int(parts[2])

    scores = ctx.user_data.setdefault("scores", [])
    scores.append(score)

    chosen = QUESTIONS[q_idx]["options"][score][0]
    await query.edit_message_text(f"{QUESTIONS[q_idx]['text']}\n\n✅ {chosen}", parse_mode="Markdown")

    next_q = q_idx + 1
    if next_q < len(QUESTIONS):
        await send_question(update, ctx, next_q)
        return Q1 + next_q
    else:
        await show_result(update, ctx)
        return ConversationHandler.END


async def show_result(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = ctx.user_data
    total = sum(data.get("scores", []))
    result = get_result(total, data.get("is_female", False))
    chat_id = update.effective_chat.id
    name_first = data.get("name", "").split()[0]
    brat = "Сестра" if data.get("is_female") else "Брат"

    await ctx.bot.send_message(chat_id=chat_id, parse_mode="Markdown",
        text=f"{result['emoji']} *{result['level']}*\nРезультат: *{result['pct']}%*\n\n{result['intro']}")

    await ctx.bot.send_message(chat_id=chat_id, parse_mode="Markdown",
        text="*Что это означает в твоей жизни:*\n\n" + "\n".join(result["pains"]))

    await ctx.bot.send_message(chat_id=chat_id, parse_mode="Markdown",
        text=f"*📊 Колесо баланса сейчас:*\n\n{result['wheel']}\n\n_После программы каждая сфера значительно вырастет._")

    await ctx.bot.send_message(chat_id=chat_id, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(result["btn"], url=result["link"])],
            [InlineKeyboardButton("📱 Открыть личный кабинет", web_app=WebAppInfo(url=MINIAPP_URL))],
            [InlineKeyboardButton("🔄 Пройти снова", callback_data="restart")],
        ]),
        text=(
            f"*{brat} {name_first}, вот твой путь:*\n\n"
            f"📍 *{result['path']}*\n_{result['path_desc']}_\n\n"
            f"{result['rec']}\n\n"
            f"🌿 _20% от каждой оплаты → благотворительность_"
        ))

    await notify_curators(ctx, update.effective_user, data, result)


async def restart_diag(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    ctx.user_data["scores"] = []
    await query.message.reply_text(
        "✨ *Начинаем заново!*\n\nКак тебя зовут? _(Имя и фамилия)_",
        parse_mode="Markdown"
    )
    return NAME


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Диагностика остановлена. Напиши /diag чтобы начать снова. 🌿",
                                    reply_markup=MAIN_MENU)
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════
#  ЭТАП 5 — ПЯТНИЧНЫЙ СОЗВОН
# ══════════════════════════════════════════════════════════════════

DEFAULT_CALL_LINK = "https://t.me/iqbarakah_bot"  # куратор меняет через /setcalllink


async def cmd_setcalllink(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Только для кураторов. /setcalllink <ссылка> — установить ссылку на созвон."""
    if update.effective_user.id not in CURATOR_IDS:
        await update.message.reply_text("⛔️ Команда только для кураторов.")
        return
    args = ctx.args
    if not args:
        current = ctx.bot_data.get("call_link", DEFAULT_CALL_LINK)
        await update.message.reply_text(
            f"Текущая ссылка: {current}\n\n"
            "Чтобы изменить: `/setcalllink https://zoom.us/j/...`",
            parse_mode="Markdown"
        )
        return
    link = args[0]
    ctx.bot_data["call_link"] = link
    await update.message.reply_text(f"✅ Ссылка обновлена:\n{link}")


async def job_friday_call(ctx: ContextTypes.DEFAULT_TYPE):
    """Пятница 13:45 МСК — напоминание о созвоне через 15 минут."""
    active = get_active_users(ctx)
    if not active:
        return
    link = ctx.bot_data.get("call_link", DEFAULT_CALL_LINK)
    count = 0
    for uid_str in active:
        try:
            await ctx.bot.send_message(
                chat_id=int(uid_str),
                parse_mode="Markdown",
                text=(
                    "📞 *Через 15 минут — живой созвон с основателем IQ Barakah!*\n\n"
                    "🕑 Сегодня в *14:00 МСК*\n\n"
                    "Это пространство где ты можешь:\n"
                    "• Задать вопрос напрямую\n"
                    "• Поделиться своим прогрессом\n"
                    "• Получить разбор своей ситуации\n\n"
                    "Приходи с одним честным вопросом. 🌿"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📞 Войти в созвон", url=link)
                ]])
            )
            count += 1
        except Exception as e:
            logger.warning(f"Friday call reminder → {uid_str}: {e}")
    logger.info(f"Пятничный созвон: напомнили {count} участникам")


async def cb_contact_curator(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_contact(update, ctx)


async def cb_my_prog(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    active = get_active_users(ctx)
    entry = active.get(uid)
    if not entry:
        await query.message.reply_text("У тебя пока нет активной программы. 🌿")
        return
    level = entry["level"]
    week  = entry["week"]
    max_w = LEVEL_WEEKS.get(level, 8)
    done  = week - 1
    bar   = "🟩" * done + "⬜️" * (max_w - done)
    pct   = round(done / max_w * 100)
    lessons = PROGRAM.get(level, [])
    next_title = lessons[week - 1]["title"] if week <= max_w and (week - 1) < len(lessons) else "Программа завершена!"
    await query.message.reply_text(
        f"📊 *Твоя программа*\n\n"
        f"📍 {LEVEL_NAMES[level]}\n"
        f"📅 Неделя *{week}* из *{max_w}*\n"
        f"Progress: {bar} {pct}%\n\n"
        f"*Следующий урок:*\n_{next_title}_",
        parse_mode="Markdown",
    )


# ══════════════════════════════════════════════════════════════════
#  ЭТАП 4 — ЯКОРНЫЙ БРАТ
# ══════════════════════════════════════════════════════════════════

def get_pairs(ctx: ContextTypes.DEFAULT_TYPE) -> dict:
    """bot_data['pairs'] = {uid: partner_uid, ...} — двусторонний словарь."""
    return ctx.bot_data.setdefault("pairs", {})


def _user_link(uid: int, name: str, username: str | None) -> str:
    if username:
        return f"[{name}](https://t.me/{username})"
    return f"[{name}](tg://user?id={uid})"


async def cmd_pair(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Только для кураторов. /pair <uid1> <uid2> — создать пару."""
    if update.effective_user.id not in CURATOR_IDS:
        await update.message.reply_text("⛔️ Команда только для кураторов.")
        return

    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "Использование: `/pair <user_id_1> <user_id_2>`\n\n"
            "Пример: `/pair 111222333 444555666`",
            parse_mode="Markdown"
        )
        return

    try:
        uid1, uid2 = int(args[0]), int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Оба аргумента должны быть числами (user_id).")
        return

    if uid1 == uid2:
        await update.message.reply_text("❌ Нельзя соединить пользователя с самим собой.")
        return

    pairs = get_pairs(ctx)
    names = ctx.bot_data.get("user_names", {})
    usernames = ctx.bot_data.get("user_usernames", {})

    name1 = names.get(str(uid1), f"Участник {uid1}")
    name2 = names.get(str(uid2), f"Участник {uid2}")
    un1   = usernames.get(str(uid1))
    un2   = usernames.get(str(uid2))

    # Разорвать старые пары если были
    for uid, partner in list(pairs.items()):
        if int(uid) in (uid1, uid2) or partner in (uid1, uid2):
            old_partner = partner if int(uid) in (uid1, uid2) else int(uid)
            pairs.pop(uid, None)
            pairs.pop(str(old_partner), None)

    # Создать новую пару (двусторонняя)
    pairs[str(uid1)] = uid2
    pairs[str(uid2)] = uid1

    link1 = _user_link(uid1, name1, un1)
    link2 = _user_link(uid2, name2, un2)

    msg1 = (
        "🤝 *Твой якорный брат назначен!*\n\n"
        f"Познакомься — это {link2}\n\n"
        "Якорный брат — это тот, кто поддерживает тебя на пути. "
        "Вы отвечаете друг другу за выполнение заданий каждую неделю.\n\n"
        "📋 *Правила якорного брата:*\n"
        "• Спрашивай его каждую пятницу: «Как прошла неделя?»\n"
        "• Честно отвечай когда спрашивают тебя\n"
        "• Делай дуа за него каждый день\n"
        "• Не осуждай — поддерживай\n\n"
        "🌿 _Напиши ему сейчас — познакомьтесь!_"
    )
    msg2 = (
        "🤝 *Твой якорный брат назначен!*\n\n"
        f"Познакомься — это {link1}\n\n"
        "Якорный брат — это тот, кто поддерживает тебя на пути. "
        "Вы отвечаете друг другу за выполнение заданий каждую неделю.\n\n"
        "📋 *Правила якорного брата:*\n"
        "• Спрашивай его каждую пятницу: «Как прошла неделя?»\n"
        "• Честно отвечай когда спрашивают тебя\n"
        "• Делай дуа за него каждый день\n"
        "• Не осуждай — поддерживай\n\n"
        "🌿 _Напиши ему сейчас — познакомьтесь!_"
    )

    notify_ok = []
    for uid, msg in ((uid1, msg1), (uid2, msg2)):
        try:
            await ctx.bot.send_message(chat_id=uid, text=msg,
                                       parse_mode="Markdown",
                                       disable_web_page_preview=True)
            notify_ok.append(str(uid))
        except Exception as e:
            logger.warning(f"Пара: не удалось уведомить {uid}: {e}")

    await update.message.reply_text(
        f"✅ *Пара создана*\n\n"
        f"🤝 {link1}  ↔  {link2}\n\n"
        f"Уведомлены: {', '.join(notify_ok) or '—'}",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


async def cmd_unpair(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Только для кураторов. /unpair <uid> — разорвать пару."""
    if update.effective_user.id not in CURATOR_IDS:
        await update.message.reply_text("⛔️ Команда только для кураторов.")
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Использование: `/unpair <user_id>`", parse_mode="Markdown")
        return
    try:
        uid = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id.")
        return

    pairs = get_pairs(ctx)
    partner_id = pairs.pop(str(uid), None)
    if partner_id:
        pairs.pop(str(partner_id), None)
        await update.message.reply_text(
            f"✅ Пара `{uid}` ↔ `{partner_id}` разорвана.", parse_mode="Markdown"
        )
        for cid in (uid, partner_id):
            try:
                await ctx.bot.send_message(
                    chat_id=cid,
                    text="ℹ️ Твоя пара якорного брата была изменена куратором. "
                         "Скоро тебе назначат нового — оставайся на пути! 🌿"
                )
            except Exception:
                pass
    else:
        await update.message.reply_text(f"Пользователь `{uid}` не в паре.", parse_mode="Markdown")


async def cmd_mybrother(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Участник смотрит кто его якорный брат."""
    uid = str(update.effective_user.id)
    # Сохранить username при каждом вызове
    user = update.effective_user
    ctx.bot_data.setdefault("user_usernames", {})[uid] = user.username

    pairs = get_pairs(ctx)
    partner_id = pairs.get(uid)

    if not partner_id:
        await update.message.reply_text(
            "🤝 *Якорный брат*\n\n"
            "У тебя пока нет якорного брата.\n\n"
            "Якорный брат назначается куратором после начала программы. "
            "Это участник который идёт рядом с тобой и поддерживает тебя каждую неделю.\n\n"
            "💬 Свяжись с куратором чтобы узнать когда будет назначен.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💬 Написать куратору", callback_data="contact_curator")
            ]])
        )
        return

    names     = ctx.bot_data.get("user_names", {})
    usernames = ctx.bot_data.get("user_usernames", {})
    p_name    = names.get(str(partner_id), f"Участник {partner_id}")
    p_un      = usernames.get(str(partner_id))
    link      = _user_link(partner_id, p_name, p_un)

    await update.message.reply_text(
        f"🤝 *Твой якорный брат*\n\n"
        f"👤 {link}\n\n"
        f"📋 *Напомни себе:*\n"
        f"• Пиши ему каждую пятницу\n"
        f"• Делай дуа за него по имени\n"
        f"• Поддерживай — не осуждай\n\n"
        f"🌿 _Баракат приходит через связь_",
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✉️ Написать ему", url=f"tg://user?id={partner_id}")
        ]])
    )


async def cmd_pairs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Только для кураторов. /pairs — список всех пар."""
    if update.effective_user.id not in CURATOR_IDS:
        await update.message.reply_text("⛔️ Команда только для кураторов.")
        return
    pairs = get_pairs(ctx)
    names = ctx.bot_data.get("user_names", {})
    if not pairs:
        await update.message.reply_text("Нет активных пар.")
        return
    seen = set()
    lines = ["👥 *Активные пары якорных братьев:*\n"]
    for uid, partner in pairs.items():
        key = tuple(sorted([uid, str(partner)]))
        if key in seen:
            continue
        seen.add(key)
        n1 = names.get(uid, f"ID {uid}")
        n2 = names.get(str(partner), f"ID {partner}")
        lines.append(f"• {n1} (`{uid}`)  🤝  {n2} (`{partner}`)")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def job_friday_checkin(ctx: ContextTypes.DEFAULT_TYPE):
    """Каждую пятницу в 10:00 МСК — напоминание написать якорному брату."""
    pairs = get_pairs(ctx)
    seen = set()
    count = 0
    for uid_str, partner_id in pairs.items():
        key = tuple(sorted([uid_str, str(partner_id)]))
        if key in seen:
            continue
        seen.add(key)
        names = ctx.bot_data.get("user_names", {})
        p_name = names.get(str(partner_id), "якорному брату").split()[0]
        for cid, pid, pn in ((int(uid_str), partner_id, p_name),
                              (partner_id, int(uid_str), names.get(uid_str, "якорному брату").split()[0])):
            try:
                await ctx.bot.send_message(
                    chat_id=cid,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                    text=(
                        f"🌟 *Пятница — время якорного брата*\n\n"
                        f"Напиши {pn} прямо сейчас:\n\n"
                        f"«Как прошла твоя неделя, брат?\n"
                        f"Что выполнил? Что было трудно?»\n\n"
                        f"🤲 И сделай дуа за него по имени.\n\n"
                        f"🌿 _Связь — это и есть умма_"
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✉️ Написать", url=f"tg://user?id={pid}"),
                        InlineKeyboardButton("📊 Мой прогресс", callback_data="my_prog"),
                    ]])
                )
                count += 1
            except Exception as e:
                logger.warning(f"Friday checkin → {cid}: {e}")
    if count:
        logger.info(f"Пятничный чек-ин якорных братьев: {count} сообщений")


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    persistence = PicklePersistence(filepath="bot_state.pkl")
    app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

    # Диалог диагностики
    MENU_BUTTONS = filters.Regex(
        "^(🎯 Диагностика|📱 Личный кабинет|📚 Программа|💳 Оплата|💰 Цены"
        "|🔔 Напоминания|🌐 Сайт|💬 Связаться с куратором)$"
    )

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("diag", cmd_diag),
            MessageHandler(filters.Regex("^🎯 Диагностика$"), cmd_diag),
            CallbackQueryHandler(cb_start_diag, pattern="^start_diag$"),
        ],
        states={
            NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTONS, got_name)],
            GENDER:     [CallbackQueryHandler(got_gender,     pattern="^gender_")],
            OCCUPATION: [CallbackQueryHandler(got_occupation, pattern="^occ_")],
            AGE:        [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTONS, got_age)],
            SOURCE:     [CallbackQueryHandler(got_source,     pattern="^src_")],
            Q1:  [CallbackQueryHandler(answer_handler, pattern="^ans_0_")],
            Q2:  [CallbackQueryHandler(answer_handler, pattern="^ans_1_")],
            Q3:  [CallbackQueryHandler(answer_handler, pattern="^ans_2_")],
            Q4:  [CallbackQueryHandler(answer_handler, pattern="^ans_3_")],
            Q5:  [CallbackQueryHandler(answer_handler, pattern="^ans_4_")],
            Q6:  [CallbackQueryHandler(answer_handler, pattern="^ans_5_")],
            Q7:  [CallbackQueryHandler(answer_handler, pattern="^ans_6_")],
            Q8:  [CallbackQueryHandler(answer_handler, pattern="^ans_7_")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(restart_diag, pattern="^restart$"),
        ],
        allow_reentry=True,
        per_user=True, per_chat=True, per_message=False,
    )

    app.add_handler(conv)

    # Статические кнопки меню
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("menu",    cmd_start))
    app.add_handler(CommandHandler("site",    cmd_site))
    app.add_handler(CommandHandler("prices",  cmd_prices))
    app.add_handler(CommandHandler("payment", cmd_payment))
    app.add_handler(MessageHandler(filters.Regex("^📱 Личный кабинет$"),          cmd_miniapp))
    app.add_handler(MessageHandler(filters.Regex("^📚 Программа$"),               cmd_program))
    app.add_handler(MessageHandler(filters.Regex("^💳 Оплата$"),                  cmd_payment))
    app.add_handler(MessageHandler(filters.Regex("^💰 Цены$"),                    cmd_prices))
    app.add_handler(MessageHandler(filters.Regex("^🌐 Сайт$"),                    cmd_site))
    app.add_handler(MessageHandler(filters.Regex("^💬 Связаться с куратором$"),   cmd_contact))
    app.add_handler(MessageHandler(filters.Regex("^🔔 Напоминания$"),             cmd_reminders))

    # Инлайн-кнопки: тарифы и оплата
    app.add_handler(CallbackQueryHandler(cb_show_tariff,  pattern="^tariff_"))
    app.add_handler(CallbackQueryHandler(cb_show_tariffs, pattern="^show_tariffs$"))
    app.add_handler(CallbackQueryHandler(cb_pay,          pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(restart_diag,    pattern="^restart$"))
    app.add_handler(CallbackQueryHandler(cb_week_ack,        pattern="^week_ack$"))
    app.add_handler(CallbackQueryHandler(cb_contact_curator, pattern="^contact_curator$"))
    app.add_handler(CallbackQueryHandler(cb_my_prog,         pattern="^my_prog$"))

    # Программа — команды для участников
    app.add_handler(CommandHandler("myprogram",   cmd_myprogram))
    app.add_handler(CommandHandler("reminders",   cmd_reminders))
    app.add_handler(CallbackQueryHandler(cb_rem_toggle,  pattern=r"^rem_toggle_"))
    app.add_handler(CallbackQueryHandler(cb_rem_off_all, pattern=r"^rem_off_all_"))
    app.add_handler(MessageHandler(filters.Regex("^📚 Программа$"), cmd_program))

    # Команды куратора
    app.add_handler(CommandHandler("activate",     cmd_activate))
    app.add_handler(CommandHandler("deactivate",   cmd_deactivate))
    app.add_handler(CommandHandler("participants", cmd_participants))
    app.add_handler(CommandHandler("sendnow",      cmd_send_now))
    app.add_handler(CommandHandler("pair",         cmd_pair))
    app.add_handler(CommandHandler("unpair",       cmd_unpair))
    app.add_handler(CommandHandler("pairs",        cmd_pairs))
    app.add_handler(CommandHandler("setcalllink",  cmd_setcalllink))

    # Якорный брат — для участников
    app.add_handler(CommandHandler("mybrother",   cmd_mybrother))
    app.add_handler(CommandHandler("mysister",    cmd_mybrother))

    # Еженедельная рассылка — каждый понедельник в 9:00 МСК (UTC+3 = 06:00 UTC)
    app.job_queue.run_daily(
        job_weekly_lesson,
        time=time(6, 0, tzinfo=timezone.utc),
        days=(0,),
        name="weekly_lesson",
    )

    # Ежедневные напоминания (МСК = UTC+3)
    async def job_morning(ctx):   await _job_reminder(ctx, "morning")
    async def job_dhuhr(ctx):     await _job_reminder(ctx, "dhuhr")
    async def job_evening(ctx):   await _job_reminder(ctx, "evening")
    async def job_muhasaba(ctx):  await _job_reminder(ctx, "muhasaba")

    app.job_queue.run_daily(job_morning,  time=REMINDER_UTC["morning"],  name="reminder_morning")
    app.job_queue.run_daily(job_dhuhr,    time=REMINDER_UTC["dhuhr"],    name="reminder_dhuhr")
    app.job_queue.run_daily(job_evening,  time=REMINDER_UTC["evening"],  name="reminder_evening")
    app.job_queue.run_daily(job_muhasaba, time=REMINDER_UTC["muhasaba"], name="reminder_muhasaba")

    # Пятничный чек-ин якорных братьев — пятница 10:00 МСК (07:00 UTC)
    app.job_queue.run_daily(
        job_friday_checkin,
        time=time(7, 0, tzinfo=timezone.utc),
        days=(4,),
        name="friday_checkin",
    )

    # Пятничный созвон — напоминание в 13:45 МСК (10:45 UTC)
    app.job_queue.run_daily(
        job_friday_call,
        time=time(10, 45, tzinfo=timezone.utc),
        days=(4,),
        name="friday_call",
    )

    print("🤖 IQ Barakah бот запущен. Ctrl+C для остановки.")
    app.run_polling()


if __name__ == "__main__":
    main()
