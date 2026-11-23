"""Approved Onyx replies; each paid synthesis is attempted at most once."""
import os
from pathlib import Path
import re

from report_bot.voice_preview import synthesize_text

ACCEPTED = 'Поручение принято. Выполню задачу на Мак и пришлю результат в этот чат.'


def spoken_summary(text):
    if text.startswith('Gmail:'):
        rows = [row[2:].split(' | ', 1)[0] for row in text.splitlines() if row.startswith('- ')]
        security = sum('Уведомление безопасности' in row for row in rows)
        topics = [row for row in rows if 'Уведомление безопасности' not in row][:4]
        if rows:
            text = f'Почта проверена. В выборке {len(rows)} непрочитанных писем.'
            if security:
                text += f' Из них уведомлений безопасности: {security}. Подробности скрыты.'
            if topics:
                text += ' Темы остальных писем: ' + '; '.join(topics) + '.'
            text += ' Полный список отправителей и тем — в текстовом отчёте.'
        else:
            text = 'Почта проверена. ' + text.splitlines()[1]
    text = re.sub(r'https?://\S+|\S+@\S+|[A-Za-z0-9_/-]{48,}', 'подробности в тексте', text)
    text = re.sub(r'[`*_#<>]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 650:
        text = text[:600].rsplit(' ', 1)[0] + '. Полный результат — в текстовом отчёте.'
    return text


async def cached_onyx(directory, key, text):
    if not re.fullmatch(r'acceptance-v1|result-[a-f0-9]{12}', key):
        raise ValueError('Invalid speech cache key')
    root = Path(directory) / 'onyx-voice'
    root.mkdir(mode=0o700, exist_ok=True)
    output = root / (key + '.ogg')
    marker = root / (key + '.started')
    if output.exists():
        return output.read_bytes()
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not api_key:
        raise ValueError('Existing OpenAI key unavailable')
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Speech already attempted; paid call not repeated') from None
    os.close(fd)
    audio = await synthesize_text(api_key, 'onyx', spoken_summary(text))
    temporary = output.with_suffix('.tmp')
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(audio)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(output)
    return audio
