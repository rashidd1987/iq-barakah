"""Контент программы и бизнес-логика прогресса.

Данные скопированы из bot.py — один источник правды.
"""

LEVEL_NAMES = {
    "А": "🌱 ВАКТ · Тайм-менеджмент мусульманина",
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
        "price": 1,
    },
    {
        "id": "s1_full",
        "name": "📗 IQ Barakah · Сезон 1",
        "desc": "Основание · КТО ты есть · 8 недель",
        "price": 10_000,
    },
    {
        "id": "s3_full",
        "name": "🏆 IQ Barakah · 3 сезона",
        "desc": "Основание + Строительство + Наследие · 24 недели",
        "price": 27_000,
    },
    {
        "id": "jamaat",
        "name": "👥 Джамаат",
        "desc": "Со-общество · до 12 человек · 24 недели",
        "price": 50_000,
    },
    {
        "id": "leader",
        "name": "👑 Лидер Уммы",
        "desc": "1 на 1 с основателем IQ Barakah · 24 недели",
        "price": 250_000,
    },
]

TARIFF_MAP = {t["id"]: t for t in TARIFFS}


def get_tariff(tariff_id: str) -> dict | None:
    return TARIFF_MAP.get(tariff_id)


def get_result(score: int, is_female: bool) -> dict:
    pct = round(score / (8 * 3) * 100)
    f = lambda m, w: w if is_female else m
    brat = "Сестра" if is_female else "Брат"

    if pct <= 25:
        return dict(level_key="А", pct=pct, emoji="🔴",
            level="Уровень А — Начинаю с нуля",
            intro=f"{brat}, это честный результат. Точка силы, не слабости.",
            path="🌱 ВАКТ — Тайм-менеджмент мусульманина")
    elif pct <= 50:
        return dict(level_key="Б", pct=pct, emoji="🔵",
            level="Уровень Б — Иногда практикую",
            intro=f"{brat}, ты уже на пути. Намаз бывает, Коран иногда. Но система не держится.",
            path="🌱 ВАКТ → 📗 Сезон 1 · Основание")
    elif pct <= 75:
        return dict(level_key="В", pct=pct, emoji="💚",
            level="Уровень В — Практикую регулярно",
            intro=f"МашаАллах, {brat.lower()}! Намаз, азкары, Коран — есть.",
            path="📗 Сезон 1 → 📘 Сезон 2 · Строительство")
    else:
        return dict(level_key="В", pct=pct, emoji="⭐️",
            level=f"Уровень В+ — Готов{f('','а')} к наследию",
            intro=f"МашаАллах, {brat.lower()}! Практика есть, система есть.",
            path="📘 Сезон 2 → 📙 Сезон 3 · Наследие")


# PROGRAM содержит полный контент уроков — импортируется из bot.py при необходимости.
# Здесь только утилиты работы с программой.

def week_progress_text(level: str, week: int) -> str:
    max_w = LEVEL_WEEKS.get(level, 8)
    done = week - 1
    pct = round(done / max_w * 100)
    return f"📅 Неделя {week}/{max_w} · {pct}% пройдено"
