"""One-off export of bot_v2 step-test quiz questions into
ACTIVE/pwa_api/content/quiz_<level>.json for the /mobile/quiz endpoint.
Re-run whenever bot_v2/services/step_tests.py changes.

Uses step_tests.get_test(level, step, skill) directly — same function the bot
itself calls — so the exported questions/answers can't drift from what the bot
actually asks.

Usage: python3 ACTIVE/pwa_api/scripts/export_quiz.py
"""
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTENT_DIR = Path(__file__).resolve().parent.parent / 'content'

LEVEL_WEEKS = {'А': 6, 'Б': 8, 'В': 8, 'Г': 8}
SKILLS = ('I', 'II', 'III')


def _load_step_tests():
    path = REPO_ROOT / 'bot_v2' / 'services' / 'step_tests.py'
    spec = importlib.util.spec_from_file_location('step_tests', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    step_tests = _load_step_tests()

    for level, max_week in LEVEL_WEEKS.items():
        weeks = []
        for week in range(1, max_week + 1):
            weeks.append({skill: step_tests.get_test(level, week, skill) for skill in SKILLS})
        out_path = CONTENT_DIR / f'quiz_{level}.json'
        out_path.write_text(json.dumps(weeks, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'{level}: {len(weeks)} weeks -> {out_path.relative_to(REPO_ROOT)}')


if __name__ == '__main__':
    main()
