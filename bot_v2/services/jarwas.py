"""AI-ментор Джарвас — обёртка над Anthropic SDK."""
import anthropic

_client: anthropic.AsyncAnthropic | None = None

JARWAS_SYSTEM = """Ты — Джарвас, AI-ментор программы IQ Barakah.
Говоришь мягко, тепло, по-братски. Только контекст программы IQ Barakah.
Коротко: 3-5 предложений. Один конкретный следующий шаг. Заканчивай тепло."""

MAX_HISTORY = 10


def setup_jarwas(api_key: str):
    global _client
    if api_key:
        _client = anthropic.AsyncAnthropic(api_key=api_key)


async def ask_jarwas(history: list[dict], user_message: str) -> str:
    if not _client:
        return "Джарвас временно недоступен. Напишите куратору. 🤍"

    history = history[-MAX_HISTORY:]
    messages = history + [{"role": "user", "content": user_message}]

    response = await _client.messages.create(
        model="claude-opus-4-7",
        max_tokens=512,
        system=JARWAS_SYSTEM,
        messages=messages,
    )
    return response.content[0].text


def parse_btn_marker(text: str) -> tuple[str, str | None]:
    """Возвращает (clean_text, btn_type | None)."""
    lines = text.strip().split("\n")
    last = lines[-1].strip()
    markers = {"[BTN:diag]", "[BTN:buy_vakt]", "[BTN:buy_s1]", "[BTN:curator]"}
    if last in markers:
        btn = last[5:-1]
        return "\n".join(lines[:-1]).strip(), btn
    return text, None
