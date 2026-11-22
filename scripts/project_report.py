"""Bounded, read-only checks of the fixed IQ Barakah GitHub main snapshot."""

import ast
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.request import Request, urlopen

REPOSITORY = 'https://github.com/rashidd1987/iq-barakah.git'
ROOT = Path.home() / '.openjarvis' / 'projects' / 'iq-barakah.git'


def wants_project_report(task):
    text = re.sub(r'[\s_-]+', '', task.casefold())
    project = any(name in text for name in ('iqbarak', 'iqbarakah', 'айкьюбарак', 'икьюбарак'))
    return project and any(word in text for word in ('провер', 'аудит', 'отч', 'состояни', 'ошиб', 'check', 'audit', 'report'))


def git(*args):
    env = {key: os.environ[key] for key in ('HOME', 'PATH', 'TMPDIR') if key in os.environ}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', LC_ALL='C')
    result = subprocess.run(['/usr/bin/git', '-c', 'core.hooksPath=/dev/null',
                             '-c', 'core.fsmonitor=false', '--git-dir=' + str(ROOT), *args],
                            env=env, capture_output=True, timeout=90, check=True)
    return result.stdout


def web_json(url):
    request = Request(url, headers={'User-Agent': 'Mizan-owner-project-report/1', 'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read(2_000_000))


def safe_name(path):
    return re.sub(r'[\x00-\x1f\x7f`]', '?', path)[:250]


def inspect_snapshot(entries, read_blob):
    """Never return source lines, credentials, data files, or executable output."""
    counts = Counter()
    findings = []
    checked = 0
    skipped = 0
    for mode, oid, size, path in entries:
        if mode not in ('100644', '100755'):
            skipped += 1
            continue
        parts = Path(path).parts
        if any(part in {'node_modules', 'vendor', 'venv', '.venv', 'dist', 'build', 'storage', 'data'} for part in parts):
            skipped += 1
            continue
        name = Path(path).name.lower()
        if name.startswith('.env') and name not in {'.env.example', '.env.sample', '.env.template'}:
            findings.append('Проверить хранение секретов: в Git отслеживается env-файл (содержимое не читалось).')
            continue
        if size > 500_000 or checked >= 1500:
            skipped += 1
            continue
        if path.endswith('.py'):
            checked += 1
            try:
                ast.parse(read_blob(oid), filename=path)
                counts['python_ok'] += 1
            except SyntaxError as exc:
                findings.append(f'Синтаксис Python: {safe_name(path)}, строка {exc.lineno}.')
            except (UnicodeError, ValueError):
                findings.append(f'Не удалось разобрать Python: {safe_name(path)}.')
        elif name == 'package.json':
            checked += 1
            try:
                package = json.loads(read_blob(oid))
                if not isinstance(package, dict):
                    raise ValueError()
                counts['package_ok'] += 1
                scripts = package.get('scripts', {})
                if not isinstance(scripts, dict) or not any(k in scripts for k in ('test', 'typecheck', 'lint')):
                    findings.append(f'Нет скрипта test/typecheck/lint: {safe_name(path)}.')
            except (ValueError, UnicodeError):
                findings.append(f'Некорректный package.json: {safe_name(path)}.')
    return counts, findings, skipped


def report(workspace):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    lines = ['# Проверка IQ Barakah', '', 'Время UTC: ' + stamp, 'Источник: GitHub rashidd1987/iq-barakah, ветка main.', '']
    success = True
    try:
        ROOT.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not ROOT.exists():
            git('init', '--bare', str(ROOT))
        git('fetch', '--depth=1', '--no-tags', REPOSITORY, 'refs/heads/main')
        sha = git('rev-parse', 'FETCH_HEAD').decode().strip()
        lines += ['Commit: ' + sha, 'Снимок main обновлён перед этой проверкой.', '']
        raw = git('ls-tree', '-rlz', sha)
        entries = []
        for item in raw.split(b'\0'):
            if not item:
                continue
            meta, path = item.split(b'\t', 1)
            mode, kind, oid, size = meta.decode().split()
            if kind == 'blob':
                entries.append((mode, oid, int(size), path.decode('utf-8', errors='replace')))
        counts, findings, skipped = inspect_snapshot(entries, lambda oid: git('cat-file', 'blob', oid))
        lines += [f'Файлов в Git: {len(entries)}.', f'Python: синтаксис проверен успешно у {counts["python_ok"]} файлов.',
                  f'Корректных package.json: {counts["package_ok"]}.', f'Пропущено по ограничениям: {skipped}.', '', '## Замечания']
        lines += findings[:25] or ['В выполненных статических проверках замечаний не найдено.']
        try:
            runs = web_json('https://api.github.com/repos/rashidd1987/iq-barakah/actions/runs?branch=main&per_page=15').get('workflow_runs', [])
            matching = [r for r in runs if r.get('head_sha') == sha and r.get('name') == 'Quality checks']
            lines += ['', '## CI для этого commit']
            if matching:
                run = matching[0]
                lines += [f'Quality checks: {run.get("status")} / {run.get("conclusion")}.',
                          f'https://github.com/rashidd1987/iq-barakah/actions/runs/{int(run["id"])}']
            else:
                lines += ['Для точного commit запуск Quality checks в последних записях не найден.']
        except Exception:
            lines += ['', 'CI: проверить не удалось; статус не подтверждён.']
    except (OSError, subprocess.SubprocessError, ValueError):
        success = False
        lines += ['Не удалось обновить или прочитать main. Старый снимок не выдаётся за актуальный.']
    try:
        with urlopen(Request('https://iq-barakah.ru/', headers={'User-Agent': 'Mizan-owner-project-report/1'}), timeout=15) as response:
            lines += ['', f'Сайт iq-barakah.ru: HTTP {response.status}. Это проверка доступности, не пользовательских сценариев.']
    except Exception:
        lines += ['', 'Сайт iq-barakah.ru: доступность не подтверждена из сети Mac.']
    lines += ['', '## Границы проверки', 'Код только читался: не запускался и не изменялся. Тесты проекта локально не выполнялись.',
              'Не проверялись: незакоммиченные локальные правки, production-база, закрытая CRM, пользовательские сценарии и зависимости на уязвимости.',
              'Это базовый технический отчёт, а не полный аудит. Для глубокого анализа и исправлений используйте задачу Codex.']
    outbox = workspace.resolve() / 'outbox'
    outbox.mkdir(parents=True, exist_ok=True)
    # Prevent a model-created symlink redirecting reports outside the workspace.
    if not outbox.resolve().is_relative_to(workspace.resolve()):
        raise ValueError('outbox outside workspace')
    target = outbox / f'iq-barakah-report-{stamp}.md'
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    text = '\n'.join(lines) + '\n'
    with os.fdopen(fd, 'w') as stream:
        stream.write(text)
    if target.read_text() != text:
        raise OSError('report verification failed')
    return {'status': 'done' if success else 'failed', 'result': text[:14000] + '\nФайл: outbox/' + target.name}
