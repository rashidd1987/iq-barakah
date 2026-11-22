"""Offline Russian voice replies. No shell, cloud TTS, or model tool access."""
import base64
from pathlib import Path
import re
import subprocess
import tempfile

MAX_AUDIO = 260000


def render_voice(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('empty speech')
    # Keep secrets, paths and URLs out of speech; full details stay in text.
    text = re.sub(r'https?://\S+|[A-Za-z0-9_/-]{48,}', ' подробности в текстовом отчёте ', text)
    text = re.sub(r'[`*_#<>]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 900:
        text = text[:850].rsplit(' ', 1)[0] + '. Полный результат — в текстовом отчёте.'
    encoder = next((p for p in ('/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg') if Path(p).is_file()), None)
    if not encoder:
        raise OSError('voice encoder unavailable')
    with tempfile.TemporaryDirectory(prefix='mizan-speech-') as folder:
        source = Path(folder) / 'speech.txt'
        source.write_text(text, encoding='utf-8'); source.chmod(0o600)
        aiff, ogg = Path(folder) / 'speech.aiff', Path(folder) / 'speech.ogg'
        subprocess.run(['/usr/bin/say', '-v', 'Milena', '-r', '175', '-f', str(source), '-o', str(aiff)],
                       check=True, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([encoder, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(aiff),
                        '-t', '65', '-c:a', 'libopus', '-b:a', '24k', '-ac', '1', str(ogg)],
                       check=True, timeout=45, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        audio = ogg.read_bytes()
        if not 500 <= len(audio) <= MAX_AUDIO or not audio.startswith(b'OggS') or b'OpusHead' not in audio[:128]:
            raise ValueError('invalid speech output')
        return base64.b64encode(audio).decode('ascii')
