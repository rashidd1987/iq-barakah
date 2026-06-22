"""AI-аналитика участников — структурированные ответы через messages.parse().

Два инструмента:
  1. analyze_participant() — куратор вызывает /analyze <uid>
     → риск, проблема, рекомендация, конкретный шаг
  2. generate_week_tip()   — рассылается участнику вместе с уроком недели
     → персональный фокус под его уровень, неделю и профиль
"""

from __future__ import annotations

import logging
from typing import Literal

import anthropic
from pydantic import BaseModel

from bot_v2.services.jarwas import JARWAS_SYSTEM

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def setup_insights(api_key: str) -> None:
    global _client
    if api_key:
        _client = anthropic.AsyncAnthropic(api_key=api_key)


# ── Схемы ────────────────────────────────────────────────────────────────────

class ParticipantInsight(BaseModel):
    risk: Literal["low", "medium", "high"]
    summary: str          # 1-2 предложения — что сейчас происходит с участником
    issue: str            # главная проблема или риск (1 предложение)
    action: str           # один конкретный шаг куратора (1 предложение)


class WeeklyTip(BaseModel):
    focus: str            # тема/фокус этой недели (3-5 слов)
    tip: str              # персональный совет участнику (2-3 предложения)
    question: str         # один рефлексивный вопрос для практики


# ── Функции ───────────────────────────────────────────────────────────────────

async def analyze_participant(
    name: str,
    level: str,
    week: int,
    occupation: str | None,
    age: str | None,
    silence_days: int,
    muhasaba_answers: list[dict],   # последние 3-5 записей из MuhasabaLog.answers
    tracker_habits: list[dict],     # последние 7 записей из TrackerRecord.habits
) -> ParticipantInsight | None:
    """Возвращает AI-анализ участника для куратора.

    Возвращает None если клиент не инициализирован или произошла ошибка.
    """
    if not _client:
        return None

    # Формируем краткое описание данных участника
    muh_text = _format_muhasaba(muhasaba_answers)
    tracker_text = _format_tracker(tracker_habits)

    prompt = (
        f"Проанализируй участника программы IQ Barakah и дай куратору рекомендацию.\n\n"
        f"ДАННЫЕ УЧАСТНИКА:\n"
        f"Имя: {name}\n"
        f"Уровень: {level}, Шаг: {week}\n"
        f"Деятельность: {occupation or 'не указана'}\n"
        f"Возраст: {age or 'не указан'}\n"
        f"Молчание в боте: {silence_days} дней\n\n"
        f"МУХАСАБА (последние записи):\n{muh_text}\n\n"
        f"ТРЕКЕР ПРИВЫЧЕК (последние 7 дней):\n{tracker_text}\n\n"
        f"Верни JSON с полями: risk (low/medium/high), summary, issue, action."
    )

    try:
        response = await _client.messages.parse(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=[{
                "type": "text",
                "text": (
                    "Ты — аналитик программы IQ Barakah. "
                    "Анализируешь данные участника и даёшь куратору краткий, "
                    "конкретный отчёт. Риск: low — всё хорошо, "
                    "medium — нужно внимание, high — срочно связаться."
                ),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
            response_format=ParticipantInsight,
        )
        return response.parsed
    except Exception as e:
        logger.warning(f"analyze_participant error: {e}")
        return None


async def generate_week_tip(
    name: str,
    level: str,
    week: int,
    occupation: str | None,
    is_female: bool,
) -> WeeklyTip | None:
    """Генерирует персональный фокус недели для участника.

    Возвращает None если клиент не инициализирован или произошла ошибка.
    """
    if not _client:
        return None

    brat = "сестра" if is_female else "брат"
    prompt = (
        f"Создай персональный фокус недели для участника.\n\n"
        f"Имя: {name} ({brat})\n"
        f"Уровень: {level}, Шаг: {week}\n"
        f"Деятельность: {occupation or 'не указана'}\n\n"
        f"Верни JSON: focus (тема недели, 3-5 слов), "
        f"tip (совет 2-3 предложения через призму программы), "
        f"question (один рефлексивный вопрос для практики)."
    )

    try:
        response = await _client.messages.parse(
            model="claude-sonnet-4-6",
            max_tokens=384,
            system=[{
                "type": "text",
                "text": JARWAS_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
            response_format=WeeklyTip,
        )
        return response.parsed
    except Exception as e:
        logger.warning(f"generate_week_tip error: {e}")
        return None


# ── Форматирование данных ─────────────────────────────────────────────────────

def _format_muhasaba(logs: list[dict]) -> str:
    if not logs:
        return "нет записей"
    lines = []
    for i, entry in enumerate(logs[-3:], 1):
        # entry = [{q: "...", a: "..."}, ...]
        answers = ", ".join(str(a.get("a", "")) for a in entry if isinstance(a, dict))
        lines.append(f"{i}. {answers[:120]}")
    return "\n".join(lines)


def _format_tracker(records: list[dict]) -> str:
    if not records:
        return "нет данных"
    # Считаем среднее выполнение намаза
    namaz_counts = []
    azkar_done = 0
    for r in records:
        namaz = r.get("namaz", {})
        if isinstance(namaz, dict):
            done = sum(1 for v in namaz.values() if v)
            namaz_counts.append(done)
        daily = r.get("daily", {})
        if isinstance(daily, dict) and daily.get("azkar"):
            azkar_done += 1

    avg_namaz = round(sum(namaz_counts) / len(namaz_counts), 1) if namaz_counts else 0
    return (
        f"Намаз в среднем: {avg_namaz}/5 в день\n"
        f"Азкары: {azkar_done}/{len(records)} дней"
    )
