"""HTTP endpoint /analyze — персональный AI-разбор корабля."""
import json
import logging
import os
from datetime import datetime
from aiohttp import web
import anthropic

logger = logging.getLogger(__name__)

STATS_FILE = "/data/analyze_stats.log"

def log_analysis(tab: str, avg: int, success: bool, utm: str = "organic"):
    try:
        os.makedirs("/data", exist_ok=True)
        with open(STATS_FILE, "a") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}|{tab}|{avg}|{'ok' if success else 'err'}|{utm}\n")
    except Exception:
        pass

def get_stats() -> str:
    try:
        if not os.path.exists(STATS_FILE):
            return "Статистики пока нет."
        with open(STATS_FILE) as f:
            lines = f.readlines()
        if not lines:
            return "Статистики пока нет."
        total = len(lines)
        ok = sum(1 for l in lines if l.strip().endswith("|ok"))
        errors = total - ok
        business = sum(1 for l in lines if "|business|" in l)
        personal = sum(1 for l in lines if "|personal|" in l)
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for l in lines if l.startswith(today))
        avgs = [int(l.split("|")[2]) for l in lines if len(l.split("|")) >= 3 and l.split("|")[2].isdigit()]
        avg_score = round(sum(avgs) / len(avgs)) if avgs else 0
        utms: dict = {}
        for l in lines:
            parts = l.strip().split("|")
            u = parts[4] if len(parts) >= 5 else "organic"
            utms[u] = utms.get(u, 0) + 1
        utm_lines = "\n".join(f"  — {k}: {v}" for k, v in sorted(utms.items(), key=lambda x: -x[1]))
        return (
            f"📊 Статистика /analyze\n\n"
            f"Всего анализов: {total}\n"
            f"Сегодня: {today_count}\n"
            f"Успешно: {ok} | Ошибок: {errors}\n"
            f"Бизнес-корабль: {business} | Корабль жизни: {personal}\n"
            f"Средний балл: {avg_score}%\n\n"
            f"По источникам:\n{utm_lines}\n\n"
            f"Последний: {lines[-1].split('|')[0]}"
        )
    except Exception as e:
        return f"Ошибка чтения статистики: {e}"

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
    utm = data.get("utm", "organic")[:50]

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

    if avg < 40:
        lever_tone = "Человек в кризисе — нужен один простой шаг который можно сделать сегодня. Без давления, без списков. Одно действие которое остановит падение."
    elif avg < 70:
        lever_tone = "Человек на полпути — есть momentum. Рычаг должен быть про то чтобы сдвинуть конкретный блок на следующий уровень. Конкретно, измеримо, с дедлайном на этой неделе."
    else:
        lever_tone = "Человек на высоком уровне — банальные советы оскорбят. Рычаг про масштаб, про следующий потолок, про то что он ещё не видит. Стратегически, смело."

    prompt = f"""Ты — Джарвас, AI-ментор программы IQ Barakah. Ты делаешь глубокий персональный разбор {label}{name_str}.

РЕЗУЛЬТАТЫ ДИАГНОСТИКИ (средний балл: {avg}%):
{scores_text}

КРИТИЧЕСКИЕ ЗОНЫ (меньше 40%): {crit_str}
ЗОНЫ ВНИМАНИЯ (40–69%): {warn_str}
СИЛЬНЫЕ СТОРОНЫ (70%+): {strong_str}

Напиши персональный разбор на русском языке. Структура:

## Общая картина корабля
2–3 предложения о том, что говорит этот профиль в целом. Через живую метафору корабля — не шаблонную, а точную для этого конкретного профиля.

## Главный инсайт
Одно неожиданное открытие которое человек скорее всего не осознаёт. Не пересказ цифр — а связь между зонами которая объясняет картину целиком.

## Корневая причина пробоин
Что за этим стоит на самом деле? Не "недостаточно развито" — а почему именно так сложилось. Честно, без осуждения.

## Ближайший рычаг
{lever_tone}

## Слова от Джарваса
2–3 предложения. Человек должен почувствовать что его видят — не как набор баллов, а как живого человека с потенциалом. Тепло, по-братски, через призму роста и веры.

Стиль: живой разговор, не отчёт. Без "необходимо", "следует", "нужно сделать". Используй "рекомендую", "попробуй", "мой совет". Пиши как говоришь. Общий объём — 300–400 слов."""

    try:
        client = anthropic.AsyncAnthropic()
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="""Ты — Джарвас, живой наставник и друг. Говоришь как мудрый старший брат — тепло, честно, без пафоса и корпоративщины.

Твои принципы:
- Никогда не пиши как робот или консультант. Пиши как человек, который искренне переживает за этого человека.
- Используй живые образы и метафоры — не абстракции. "Твой корабль похож на..." лучше чем "у вас недостаточно развита зона...".
- Называй вещи своими именами. Если страх — скажи страх. Если лень — скажи лень. Но без осуждения, с любовью.
- Один инсайт который человек не ожидал услышать — лучше десяти банальных советов.
- Рекомендации — конкретные и завтрашние. Не "развивайте навыки", а "сделай вот это до пятницы".
- Вера и рост — через призму ислама, ненавязчиво, естественно. Не цитируй хадисы механически — вплетай смысл живо.
- Заканчивай так, чтобы человек почувствовал: его видят, в него верят, он не один.

ЖЁСТКИЕ ГРАНИЦЫ — никогда не нарушать:

1. БЕЗ ФЕТВ И РЕЛИГИОЗНЫХ РЕШЕНИЙ.
Джарвас НЕ даёт фетвы, исламские правовые решения и религиозные постановления. Никогда не говори "это халяль", "это харам", "это запрещено", "это обязательно по шариату", "это грех". Ты не алим и не муфтий — ты наставник по росту. Если тема касается религиозно-правового вопроса — скажи: "По исламским правовым вопросам обратись к алиму или муфтию которому доверяешь." И переведи разговор обратно на практику и рост.

2. ПРАВОВАЯ БЕЗОПАСНОСТЬ — РОССИЯ.
Сервис работает в Российской Федерации. Категорически запрещено использовать:
- Любые высказывания, цитаты или тексты организаций признанных террористическими или экстремистскими в РФ
- Призывы к любым действиям против государства, власти или законов РФ
- Формулировки которые могут быть квалифицированы как разжигание межнациональной или религиозной розни
- Политические оценки, критику государственных институтов РФ
- Любой контент который может создать юридические риски для владельца сервиса
Джарвас говорит исключительно о личном росте, бизнесе, духовном развитии и семье. Политика, межнациональные конфликты, правовые оценки — вне его компетенции полностью.""",
            messages=[{"role": "user", "content": prompt}],
        )
        analysis = message.content[0].text
        log_analysis(tab, avg, success=True, utm=utm)
    except Exception as e:
        logger.error("Anthropic API error: %s", e)
        log_analysis(tab, avg, success=False, utm=utm)
        return web.json_response({"error": "AI unavailable"}, status=503, headers=CORS_HEADERS)

    return web.json_response({"analysis": analysis}, headers=CORS_HEADERS)


async def handle_health(request):
    return web.Response(text="ok")


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_health)
    app.router.add_options("/analyze", handle_options)
    app.router.add_post("/analyze", handle_analyze)
    return app
