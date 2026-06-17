"""Контент программы и бизнес-логика прогресса.

Данные скопированы из bot.py — один источник правды.
"""

LEVEL_NAMES = {
    "А": "🌱 IQ Barakah Старт",
    "Б": "📗 IQ Barakah · Сезон 1 · Основание",
    "В": "📘 IQ Barakah · Сезон 2 · Строительство",
    "Г": "📙 IQ Barakah · Сезон 3 · Наследие",
}

LEVEL_WEEKS = {"А": 6, "Б": 8, "В": 8, "Г": 8}

TARIFFS = [
    {
        "id": "vakt",
        "name": "🌱 ВАКТ",
        "desc": "Тайм-менеджмент мусульманина · 6 недель",
        "price": 100,
    },
    {
        "id": "s1_month",
        "name": "📗 IQ Barakah · Сезон 1",
        "desc": "Основание · 8 недель · помесячно",
        "price": 5_000,
    },
    {
        "id": "s1_full",
        "name": "📗 IQ Barakah · Сезон 1",
        "desc": "Основание · КТО ты есть · 8 недель · полный доступ",
        "price": 10_000,
    },
    {
        "id": "s3_full",
        "name": "🏆 IQ Barakah · 3 сезона",
        "desc": "Основание + Строительство + Наследие · 24 недели",
        "price": 27_000,
    },
    {
        "id": "forum_27_06",
        "name": "🎟 Форум 27 июня · Шатёр",
        "desc": "Вход на форум + IQ Barakah Старт (6 шагов) + обед в Шатёр",
        "price": 1500,
    },
    {
        "id": "jamaat",
        "name": "👥 Джамаат",
        "desc": "Со-общество · до 12 человек · 24 недели",
        "price": 0,
    },
    {
        "id": "leader",
        "name": "👑 Лидер Уммы",
        "desc": "1 на 1 с основателем IQ Barakah · 24 недели",
        "price": 0,
    },
]

TARIFF_MAP = {t["id"]: t for t in TARIFFS}

TARIFF_TEXTS = {
    "ru": {
        "vakt": ("🌱 ВАКТ", "Тайм-менеджмент мусульманина · 6 недель"),
        "s1_full": ("📗 IQ Barakah · Сезон 1", "Основание · КТО ты есть · 8 недель"),
        "s3_full": ("🏆 IQ Barakah · 3 сезона", "Основание + Строительство + Наследие · 24 недели"),
        "jamaat": ("👥 Джамаат", "Со-общество · до 12 человек · 24 недели"),
        "leader": ("👑 Лидер Уммы", "1 на 1 с основателем IQ Barakah · 24 недели"),
    },
    "en": {
        "vakt": ("🌱 VAKT", "Muslim time management · 6 weeks"),
        "s1_full": ("📗 IQ Barakah · Season 1", "Foundation · Who you are · 8 weeks"),
        "s3_full": ("🏆 IQ Barakah · 3 seasons", "Foundation + Building + Legacy · 24 weeks"),
        "jamaat": ("👥 Jamaat", "Community cohort · up to 12 people · 24 weeks"),
        "leader": ("👑 Ummah Leader", "1-on-1 with the founder of IQ Barakah · 24 weeks"),
    },
    "ar": {
        "vakt": ("🌱 VAKT", "إدارة وقت المسلم · 6 أسابيع"),
        "s1_full": ("📗 IQ Barakah · الموسم 1", "الأساس · من أنت · 8 أسابيع"),
        "s3_full": ("🏆 IQ Barakah · 3 مواسم", "الأساس + البناء + الأثر · 24 أسبوعاً"),
        "jamaat": ("👥 الجماعة", "مجموعة تعليمية · حتى 12 شخصاً · 24 أسبوعاً"),
        "leader": ("👑 قائد الأمة", "جلسات فردية مع مؤسس IQ Barakah · 24 أسبوعاً"),
    },
    "tr": {
        "vakt": ("🌱 VAKT", "Müslüman için zaman yönetimi · 6 hafta"),
        "s1_full": ("📗 IQ Barakah · Sezon 1", "Temel · Kimsin · 8 hafta"),
        "s3_full": ("🏆 IQ Barakah · 3 sezon", "Temel + İnşa + Miras · 24 hafta"),
        "jamaat": ("👥 Cemaat", "Topluluk grubu · en fazla 12 kişi · 24 hafta"),
        "leader": ("👑 Ümmet Lideri", "IQ Barakah kurucusuyla bire bir · 24 hafta"),
    },
}


def get_tariff(tariff_id: str) -> dict | None:
    return TARIFF_MAP.get(tariff_id)


def get_tariff_view(tariff_id: str, lang: str | None = "ru") -> dict | None:
    tariff = get_tariff(tariff_id)
    if not tariff:
        return None
    lang = (lang or "ru").lower().split("-")[0]
    name, desc = TARIFF_TEXTS.get(lang, TARIFF_TEXTS["ru"]).get(
        tariff_id,
        (tariff["name"], tariff["desc"]),
    )
    return {**tariff, "name": name, "desc": desc}


def get_result(score: int, is_female: bool) -> dict:
    pct = round(score / (8 * 3) * 100)
    f = lambda m, w: w if is_female else m
    brat = "Сестра" if is_female else "Брат"

    if pct <= 25:
        return dict(level_key="А", pct=pct, emoji="🔴",
            level="I — Пробуждение (делаю первые шаги)",
            intro=f"{brat}, это честный результат. Точка силы, не слабости.",
            path="🌱 ВАКТ — Тайм-менеджмент мусульманина")
    elif pct <= 50:
        return dict(level_key="Б", pct=pct, emoji="🔵",
            level="II — Практика (встраиваю в жизнь)",
            intro=f"{brat}, ты уже на пути. Намаз бывает, Коран иногда. Но система не держится.",
            path="🌱 ВАКТ → 📗 Сезон 1 · Основание")
    elif pct <= 75:
        return dict(level_key="В", pct=pct, emoji="💚",
            level="III — Баракат (это часть меня, живу с благословением)",
            intro=f"МашаАллах, {brat.lower()}! Намаз, азкары, Коран — есть.",
            path="📗 Сезон 1 → 📘 Сезон 2 · Строительство")
    else:
        return dict(level_key="В", pct=pct, emoji="⭐️",
            level="III — Баракат (это часть меня, живу с благословением)",
            intro=f"МашаАллах, {brat.lower()}! Практика есть, система есть.",
            path="📘 Сезон 2 → 📙 Сезон 3 · Наследие")


# PROGRAM содержит полный контент уроков — импортируется из bot.py при необходимости.
# Здесь только утилиты работы с программой.

def week_progress_text(level: str, week: int) -> str:
    max_w = LEVEL_WEEKS.get(level, 8)
    done = week - 1
    pct = round(done / max_w * 100)
    return f"📅 Шаг {week}/{max_w} · {pct}% пройдено"
