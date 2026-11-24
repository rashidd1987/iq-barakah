"""Free CPU-only Russian server speech. No external TTS requests."""
import base64
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def render_voice(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('empty speech')
    text = re.sub(r'https?://\S+|[A-Za-z0-9_/-]{48,}', ' подробности в текстовом отчёте ', text)
    text = re.sub(r'[`*_#<>]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 900:
        text = text[:850].rsplit(' ', 1)[0] + '. Полный результат — в текстовом отчёте.'
    model = Path.home() / '.openjarvis' / 'voices' / 'ru_RU-denis-medium.onnx'
    if not model.is_file() or not model.with_suffix('.onnx.json').is_file():
        raise OSError('server voice not installed')
    with tempfile.TemporaryDirectory(prefix='mizan-speech-') as folder:
        wav, ogg = Path(folder) / 'speech.wav', Path(folder) / 'speech.ogg'
        subprocess.run([sys.executable, '-m', 'piper', '--model', str(model),
                        '--output_file', str(wav)], input=text, text=True,
                       check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['/usr/bin/ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-i', str(wav), '-t', '65', '-c:a', 'libopus', '-b:a', '24k',
                        '-ac', '1', str(ogg)], check=True, timeout=45,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        audio = ogg.read_bytes()
        if not 500 <= len(audio) <= 260000 or not audio.startswith(b'OggS') or b'OpusHead' not in audio[:128]:
            raise ValueError('invalid server speech')
        return base64.b64encode(audio).decode('ascii')
