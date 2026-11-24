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
        folder = Path(folder)
        ogg = folder / 'speech.ogg'
        # Long VITS inputs consume disproportionate RAM on the small owner VPS.
        # Bound each inference, preserve word order, and join PCM before encoding.
        chunks = speech_chunks(text)
        for index, chunk in enumerate(chunks):
            wav = folder / f'part-{index}.wav'
            subprocess.run([sys.executable, '-m', 'piper', '--model', str(model),
                            '--output_file', str(wav)], input=chunk, text=True,
                           check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        listing = folder / 'parts.txt'
        listing.write_text(''.join(f"file 'part-{i}.wav'\n" for i in range(len(chunks))))
        subprocess.run(['/usr/bin/ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'concat', '-safe', '1', '-i', str(listing),
                        '-t', '65', '-c:a', 'libopus', '-b:a', '24k',
                        '-ac', '1', str(ogg)], check=True, timeout=45,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        audio = ogg.read_bytes()
        if not 500 <= len(audio) <= 260000 or not audio.startswith(b'OggS') or b'OpusHead' not in audio[:128]:
            raise ValueError('invalid server speech')
        return base64.b64encode(audio).decode('ascii')


def speech_chunks(text, limit=75):
    chunks = []
    while text:
        end = min(len(text), limit)
        if len(text) > limit:
            boundary = text.rfind(' ', 0, limit + 1)
            if boundary > 0:
                end = boundary
        chunks.append(text[:end])
        text = text[end:].lstrip()
    return chunks
