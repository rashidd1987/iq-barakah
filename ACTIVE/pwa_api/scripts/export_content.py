"""One-off export of bot_v2 lesson content into ACTIVE/pwa_api/content/<level>.json
for the /mobile/content endpoint to serve read-only. Re-run whenever bot_v2's
content_vakt.py / content_s1.py / content_s2.py / content_s3.py change.

Usage: python3 ACTIVE/pwa_api/scripts/export_content.py
"""
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTENT_DIR = Path(__file__).resolve().parent.parent / 'content'

SOURCES = {
    'А': ('content_vakt', 'VAKT'),
    'Б': ('content_s1', 'SEASON1'),
    'В': ('content_s2', 'SEASON2'),
    'Г': ('content_s3', 'SEASON3'),
}


def _load_module(module_file: str):
    path = REPO_ROOT / 'bot_v2' / 'services' / f'{module_file}.py'
    spec = importlib.util.spec_from_file_location(module_file, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    for level, (module_file, attr) in SOURCES.items():
        module = _load_module(module_file)
        weeks = getattr(module, attr)
        out_path = CONTENT_DIR / f'{level}.json'
        out_path.write_text(json.dumps(weeks, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'{level}: {len(weeks)} weeks -> {out_path.relative_to(REPO_ROOT)}')


if __name__ == '__main__':
    main()
