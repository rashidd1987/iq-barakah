"""OpenAI-backed voice transcription and task draft extraction."""

from dataclasses import dataclass
from datetime import date
import json
import os

import aiohttp


@dataclass(frozen=True)
class VoiceTaskDraft:
    title: str
    due_date: date
    success_criterion: str


async def transcribe_voice(
    session: aiohttp.ClientSession,
    api_key: str,
    audio: bytes,
    *,
    filename: str = "voice.ogg",
) -> str:
    if not api_key:
        raise ValueError("OPENAI_API_KEY не настроен для распознавания голоса")
    if not audio:
        raise ValueError("Голосовое сообщение пустое")
    if len(audio) > 20 * 1024 * 1024:
        raise ValueError("Голосовое сообщение больше 20 МБ")
    form = aiohttp.FormData()
    form.add_field(
        "file",
        audio,
        filename=filename,
        content_type="audio/ogg",
    )
    form.add_field(
        "model",
        os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe").strip(),
    )
    form.add_field("language", "ru")
    timeout = aiohttp.ClientTimeout(total=120)
    async with session.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        data=form,
        timeout=timeout,
    ) as response:
        payload = await response.json(content_type=None)
        if response.status >= 400:
            raise RuntimeError(f"OpenAI transcription returned HTTP {response.status}")
    text = str(payload.get("text", "")).strip() if isinstance(payload, dict) else ""
    if not text:
        raise RuntimeError("Не удалось распознать речь")
    return text[:4000]


async def extract_voice_task(
    session: aiohttp.ClientSession,
    api_key: str,
    transcript: str,
    *,
    today: date,
) -> VoiceTaskDraft:
    if not api_key:
        raise ValueError("OPENAI_API_KEY не настроен")
    prompt = (
        "Преобразуй русскую голосовую заметку собственника в задачу. "
        f"Сегодня {today.isoformat()}. Разрешай относительные даты вроде завтра. "
        "Верни только JSON: title, due_date в YYYY-MM-DD, success_criterion. "
        "Не выдумывай срок: если его нет, due_date должен быть null. "
        "Критерий готовности сформулируй проверяемо и кратко.\n\n"
        f"Заметка: {transcript}"
    )
    timeout = aiohttp.ClientTimeout(total=90)
    async with session.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    ) as response:
        payload = await response.json(content_type=None)
        if response.status >= 400:
            raise RuntimeError(f"OpenAI task extraction returned HTTP {response.status}")
    try:
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        title = str(parsed.get("title", "")).strip()
        criterion = str(parsed.get("success_criterion", "")).strip()
        due_raw = parsed.get("due_date")
        if not due_raw:
            raise ValueError(
                "В голосовом сообщении не найден срок. Назовите дату и отправьте снова."
            )
        due = date.fromisoformat(str(due_raw))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("ИИ вернул некорректный черновик задачи") from exc
    if not 3 <= len(title) <= 300:
        raise ValueError("Не удалось определить короткое название задачи")
    if not 3 <= len(criterion) <= 500:
        raise ValueError("Не удалось определить критерий готовности")
    if due < today:
        raise ValueError("Срок из голосового сообщения уже прошёл")
    return VoiceTaskDraft(title, due, criterion)
