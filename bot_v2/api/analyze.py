"""HTTP endpoint /analyze — персональный AI-разбор корабля."""
import json
import logging
from aiohttp import web
import anthropic

logger = logging.getLogger(__name__)

BUSINESS_BLOCKS = [
    "Энергия основателя","Ният и мышление","Самореализация и зона гения",
    "Ценность и трансформация","Команда и экипаж","Продукт и сервис",
    "Маркетинг и охват","Продажи и конверсия","Финансы и прибыль",
    "Системы и процессы","Стратегия и видение","Партнёрства и сети",
    "Устойчивость и антихрупкость","Лидерство и влияние","Наследие и вклад",
]

PERSONAL_BLOCKS = [
    "Тело и здоровье","Духовность и ибадат","Ниет и самопознание",
    "Семья и близкие","Финансы личные","Профессия и реализация",
    "Знание и рост","Окружение и уммат","Благотворительность",
    "Психология и эмоции","Отдых и восстановление","Время и приоритеты",
    "Мечты и цели","Наследие","Гармония и баланс",
]

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


async def handle_options(request):
    return web.Response(headers=CORS_HEADERS)


async def handle_analyze(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400, headers=CORS_HEADERS)

    scores = data.get("scores", [])
    name = data.get("name", "").strip()
    tab = data.get("tab", "business")

    if len(scores) != 15:
        return web.json_response({"error": "Expected 15 scores"}, status=400, headers=CORS_HEADERS)

    blocks = BUSINESS_BLOCKS if tab == "business" else PERSONAL_BLOCKS
    label = "бизнес-корабля" if tab == "business" else "корабля жизни"

    scores_text = "\n".join(
        f"  {i+1}. {blocks[i]}: {scores[i]}%" for i in range(15)
    )
    avg = round(sum(scores) / 15)
    crit = [blocks[i] for i, s in enumerate(scores) if s < 40]
    warn = [blocks[i] for i, s in enumerate(scores) if 40 <= s < 70]
    strong = [blocks[i] for i, s in enumerate(scores) if s >= 70]

    name_str = f" для {name}" if name else ""
    crit_str = ", ".join(crit) if crit else "нет критических зон"
    warn_str = ", ".join(warn) if warn else "нет"
    strong_str = ", ".join(strong) if strong else "нет"

    prompt = f"""Ты — Джарвас, AI-ментор программы IQ Barakah. Ты делаешь глубокий персональный разбор {label}{name_str}.

РЕЗУЛЬТАТЫ ДИАГНОСТИКИ (средний балл: {avg}%):
{scores_text}

КРИТИЧЕСКИЕ ЗОНЫ (меньше 40%): {crit_str}
ЗОНЫ ВНИМАНИЯ (40–69%): {warn_str}
СИЛЬНЫЕ СТОРОНЫ (70%+): {strong_str}

Напиши персональный разбор на русском языке. Структура:

## Общая картина корабля
2–3 предложения о том, что говорит этот профиль в целом. Через метафору корабля.

## Главный инсайт
Самое важное открытие из этих результатов — то, что человек возможно не осознаёт. Одна ключевая связь между несколькими зонами.

## Корневая причина пробоин
Почему именно эти зоны оказались критическими? Что объединяет слабые места? Глубокий анализ, не поверхностный.

## Ближайший рычаг
Одно конкретное действие которое даст наибольший эффект прямо сейчас. Очень конкретно, измеримо, с дедлайном.

## Слова от Джарваса
2–3 предложения поддержки и веры в человека. Тепло, по-братски, через призму ислама и роста.

Стиль: живой, без канцелярщины, тепло но честно. Общий объём — 300–400 слов."""

    try:
        client = anthropic.AsyncAnthropic()
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        analysis = message.content[0].text
    except Exception as e:
        logger.error("Anthropic API error: %s", e)
        return web.json_response({"error": "AI unavailable"}, status=503, headers=CORS_HEADERS)

    return web.json_response({"analysis": analysis}, headers=CORS_HEADERS)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_options("/analyze", handle_options)
    app.router.add_post("/analyze", handle_analyze)
    return app
