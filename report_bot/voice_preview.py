"""One paid voice preview, cached permanently; never retries a synthesis call."""
import os
from pathlib import Path

import aiohttp

TEXT = ('Привет, Рашид. Поручение принято. Я проверю почту и пришлю краткий отчёт. '
        'Ты можешь отправлять задачи голосом — я приму их и сообщу результат в этом чате.')


def preview_instructions(voice):
    if voice == 'echo':
        return ('Speak Russian in a natural male voice. Be energetic, friendly and quick-witted: '
                'a capable personal assistant with a smile in the voice and understated dry humor. '
                'Crisp, nimble pacing with natural pauses; confident and reassuring. '
                'Avoid flat robotic rhythm, announcer delivery, shouting or exaggerated acting.')
    if voice == 'fable':
        return ('Speak Russian in a warm expressive male voice. Sound upbeat, charming and friendly, '
                'like a trusted teammate who enjoys solving problems. Lively intonation, subtle playful '
                'wit and a relaxed conversational smile. Moderately brisk pace, clear natural pauses. '
                'Avoid robotic delivery, a sales pitch, shouting or exaggerated acting.')
    return ('Speak in Russian with a natural male conversational voice. Warm, calm, confident. '
            'Medium pace, short natural pauses. No announcer delivery, no exaggerated emotion.')


async def synthesize_text(api_key, voice, text):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
        async with session.post('https://api.openai.com/v1/audio/speech',
                headers={'Authorization': 'Bearer ' + api_key},
                json={'model': 'gpt-4o-mini-tts', 'voice': voice, 'input': text,
                      'instructions': preview_instructions(voice),
                      'response_format': 'opus'}) as response:
            if response.status != 200:
                raise RuntimeError('Voice preview provider returned HTTP ' + str(response.status))
            audio = bytearray()
            async for chunk in response.content.iter_chunked(8192):
                audio.extend(chunk)
                if len(audio) > 2 * 1024 * 1024:
                    raise ValueError('Voice preview exceeds limit')
    audio = bytes(audio)
    if len(audio) < 500 or not audio.startswith(b'OggS') or b'OpusHead' not in audio[:128]:
        raise ValueError('Invalid voice preview format')
    return audio


async def synthesize_preview(api_key, voice="cedar"):
    return await synthesize_text(api_key, voice, TEXT)


async def cached_preview(directory, voice="cedar"):
    if voice not in {'cedar', 'onyx', 'ash', 'echo', 'fable'}:
        raise ValueError('Unsupported preview voice')
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    output = root / f'voice-preview-{voice}-v1.ogg'
    marker = root / f'voice-preview-{voice}-v1.started'
    if output.exists():
        return output.read_bytes()
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not api_key:
        raise ValueError('Existing OpenAI key unavailable')
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Preview already started; paid synthesis will not be repeated') from None
    os.close(fd)
    audio = await synthesize_preview(api_key, voice)
    temporary = output.with_suffix('.tmp')
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(audio)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(output)
    return audio
