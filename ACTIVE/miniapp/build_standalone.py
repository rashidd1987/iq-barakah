from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT.parent / "miniapp.html"

MODULES = [
    "utils/tg.js",
    "utils/storage.js",
    "utils/stats.js",
    "data/weeks.js",
    "data/habits.js",
    "data/tasks.js",
    "data/content.js",
    "data/summaries.js",
    "data/vakt_summaries.js",
    "data/glossary.js",
    "data/step_tests.js",
    "i18n.js",
    "components/sheets.js",
    "components/diagnostic.js",
    "screens/home.js",
    "screens/tracker.js",
    "screens/lessons.js",
    "screens/wheel.js",
    "screens/ship.js",
    "app.js",
    "main.js",
]


def _strip_imports(js: str) -> str:
    js = re.sub(r"^import\s+['\"][^'\"]+['\"]\s*\n", "", js, flags=re.MULTILINE)
    js = re.sub(r"^import\s+[^;\n]+(?:;)?\n", "", js, flags=re.MULTILINE)
    js = js.replace("import('../app.js').then(m => m.switchScreen('lessons'))", "switchScreen('lessons')")
    return js


def _strip_exports(js: str) -> str:
    js = re.sub(r"^export\s+(const|let|var|function|class)\s+", r"\1 ", js, flags=re.MULTILINE)
    js = re.sub(r"^export\s*\{[^}]+\}\s*;?\n", "", js, flags=re.MULTILINE)
    return js


def build_bundle() -> str:
    parts = []
    for rel in MODULES:
        path = SRC / rel
        js = path.read_text(encoding="utf-8")
        js = _strip_imports(js)
        js = _strip_exports(js)
        parts.append(f"\n// --- {rel} ---\n{js.rstrip()}\n")
    return "\n".join(parts)


def build_html() -> str:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (SRC / "style.css").read_text(encoding="utf-8")
    bundle = build_bundle()

    html = html.replace("</head>", f"  <style>\n{css}\n  </style>\n</head>")
    _replacement = f"\n<script>\n{bundle}\n</script>\n"
    html = re.sub(
        r"\s*<script\s+type=\"module\"\s+src=\"/src/main\.js\"></script>\s*",
        lambda m: _replacement,
        html,
    )
    return html


def main() -> None:
    html = build_html()
    OUT.write_text(html, encoding="utf-8")
    print(f"Built {OUT}")


if __name__ == "__main__":
    main()
