"""Small, explicit gateway for owner-approved AI council requests."""

from dataclasses import dataclass
import os

import aiohttp

from report_bot.config import AIProviderSecrets


@dataclass(frozen=True)
class AIProvider:
    key: str
    title: str
    model_env: str
    default_model: str
    endpoint: str
    kind: str = "openai"

    @property
    def model(self) -> str:
        return os.environ.get(self.model_env, self.default_model).strip()


AI_PROVIDERS = (
    AIProvider("openai", "GPT", "OPENAI_MODEL", "gpt-4.1-mini", "https://api.openai.com/v1/chat/completions"),
    AIProvider("anthropic", "Claude", "ANTHROPIC_MODEL", "claude-sonnet-4-20250514", "https://api.anthropic.com/v1/messages", "anthropic"),
    AIProvider("gemini", "Gemini", "GEMINI_MODEL", "gemini-2.5-flash", "https://generativelanguage.googleapis.com/v1beta", "gemini"),
    AIProvider("perplexity", "Perplexity", "PERPLEXITY_MODEL", "sonar", "https://api.perplexity.ai/chat/completions"),
    AIProvider("xai", "Grok", "XAI_MODEL", "grok-3-mini", "https://api.x.ai/v1/chat/completions"),
    AIProvider("deepseek", "DeepSeek", "DEEPSEEK_MODEL", "deepseek-chat", "https://api.deepseek.com/chat/completions"),
    AIProvider("kimi", "Kimi", "KIMI_MODEL", "moonshot-v1-32k", "https://api.moonshot.ai/v1/chat/completions"),
)
AI_PROVIDERS_BY_KEY = {provider.key: provider for provider in AI_PROVIDERS}

SYSTEM_PROMPT = """Ты — совет директоров владельца цифровых продуктов.
Ответь по-русски, конкретно и кратко. Рассмотри задачу как CEO, CTO, CPO,
CMO, CCO, CFO, CISO и критик. Дай: 1) вердикт; 2) три варианта;
3) рекомендацию; 4) риски; 5) безопасный следующий шаг.
Не утверждай, что выполнил изменения. Не запрашивай и не раскрывай секреты."""


def provider_titles(keys: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        AI_PROVIDERS_BY_KEY[key].title
        for key in keys
        if key in AI_PROVIDERS_BY_KEY
    )


def choose_auto_provider(task: str, configured: tuple[str, ...]) -> str:
    normalized = task.casefold()
    preferences: tuple[str, ...]
    if any(word in normalized for word in ("найди", "исслед", "новост", "рынок")):
        preferences = ("perplexity", "gemini", "openai")
    elif any(
        word in normalized
        for word in ("код", "архитект", "ошиб", "безопас", "баг", "api")
    ):
        preferences = ("anthropic", "openai", "deepseek")
    else:
        preferences = ("openai", "gemini", "anthropic", "deepseek")
    for key in preferences:
        if key in configured:
            return key
    return configured[0] if configured else ""


def choose_judge(configured: tuple[str, ...]) -> str:
    for key in ("openai", "anthropic", "gemini", "deepseek", "xai", "kimi"):
        if key in configured:
            return key
    return configured[0] if configured else ""


def synthesis_task(
    original_task: str,
    results: tuple[tuple[str, str], ...],
) -> str:
    sections = []
    for provider_key, result in results:
        title = AI_PROVIDERS_BY_KEY[provider_key].title
        sections.append(f"### {title}\n{result[:2200]}")
    joined = "\n\n".join(sections)
    return (
        "Ты — независимый председатель совета. Синтезируй ответы моделей, "
        "не голосуй по большинству. Укажи: общий вердикт, разногласия, "
        "лучший вариант, риски и один следующий безопасный шаг. "
        "Не утверждай, что действия уже выполнены.\n\n"
        f"Исходная задача: {original_task}\n\n{joined}"
    )


async def ask_ai(
    session: aiohttp.ClientSession,
    secrets: AIProviderSecrets,
    provider_key: str,
    task: str,
) -> str:
    provider = AI_PROVIDERS_BY_KEY.get(provider_key)
    secret = secrets.for_provider(provider_key)
    if provider is None or not secret:
        raise ValueError("AI provider is not configured")

    timeout = aiohttp.ClientTimeout(total=90)
    if provider.kind == "anthropic":
        headers = {
            "x-api-key": secret,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": provider.model,
            "max_tokens": 1400,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": task}],
        }
        async with session.post(
            provider.endpoint, headers=headers, json=payload, timeout=timeout
        ) as response:
            data = await _response_json(response)
        return str(data["content"][0]["text"]).strip()

    if provider.kind == "gemini":
        endpoint = f"{provider.endpoint}/models/{provider.model}:generateContent"
        headers = {"x-goog-api-key": secret, "Content-Type": "application/json"}
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": task}]}],
            "generationConfig": {"maxOutputTokens": 1400},
        }
        async with session.post(
            endpoint, headers=headers, json=payload, timeout=timeout
        ) as response:
            data = await _response_json(response)
        return str(data["candidates"][0]["content"]["parts"][0]["text"]).strip()

    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": provider.model,
        "max_tokens": 1400,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ],
    }
    async with session.post(
        provider.endpoint, headers=headers, json=payload, timeout=timeout
    ) as response:
        data = await _response_json(response)
    return str(data["choices"][0]["message"]["content"]).strip()


async def _response_json(response: aiohttp.ClientResponse) -> dict:
    data = await response.json(content_type=None)
    if response.status >= 400:
        raise RuntimeError(f"AI provider returned HTTP {response.status}")
    if not isinstance(data, dict):
        raise RuntimeError("AI provider returned an invalid response")
    return data
