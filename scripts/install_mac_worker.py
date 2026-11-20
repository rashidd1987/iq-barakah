"""Install the local runtime. Pairing is a separate interactive Terminal step."""

import argparse
import json
import os
from pathlib import Path
import plistlib
import secrets
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', metavar='REPORTS_HTTPS_URL')
    args = parser.parse_args()
    os.umask(0o077)
    root = Path.home() / '.openjarvis'
    runtime = root / 'mac-worker'
    runtime.mkdir(parents=True, exist_ok=True)
    runtime.chmod(0o700)
    workspace = Path.home() / 'Documents' / 'Mizan Assistant'
    for directory in ('inbox', 'outbox', 'code'):
        (workspace / directory).mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent
    for filename in ('mac_worker.py', 'mac_assistant.py', 'install_mac_worker.py'):
        destination = runtime / filename
        if source / filename != destination:
            shutil.copy2(source / filename, destination)
    (workspace / 'README.txt').write_text(
        'Mizan Assistant — рабочая папка локального помощника\n\n'
        'inbox/ — положите сюда исходные тексты и код (TXT, MD, JSON, CSV).\n'
        'outbox/ — готовые документы. code/ — черновики кода.\n'
        'Помощник читает и пишет только в этой папке.\n'
        'После серверного подключения: /mac задача и /macstatus в @mizan_project_reports_bot.\n'
        'Mac должен быть включён, не спать и иметь интернет.\n'
        'Модель 2B подходит для простых поручений. Изменения проектов через PR выполняет Codex в Mizan.\n'
        'Подключение пока не считается проверенным, пока тестовая задача не вернулась через Telegram.\n'
    )
    if not args.pair:
        print('Local runtime prepared. Telegram pairing is not active.')
        return
    from mac_worker import validate_config, atomic_json, api
    path = root / 'mac-worker.json'
    config = json.loads(path.read_text()) if path.exists() else {
        'secret': secrets.token_urlsafe(48), 'workspace': str(workspace)
    }
    config['reports_url'] = args.pair.rstrip('/')
    validate_config(config)
    atomic_json(path, config)
    print('В Amvera у приложения mizan-reports-bot добавьте секретную переменную MAC_WORKER_SECRET:')
    print(config['secret'])
    input('После развёртывания серверного кода и настройки переменной нажмите Enter: ')
    try:
        api(config, '/mac-worker/running')
    except Exception:
        print('Сервер не подтвердил подключение. Автозапуск не включён. Проверьте адрес, код и секрет.')
        return 1
    python = root / '.venv' / 'bin' / 'python'
    log_dir = root / '.state'
    log_dir.mkdir(exist_ok=True)
    plist = Path.home() / 'Library/LaunchAgents/ru.mizan.mac-worker.plist'
    plist.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'Label': 'ru.mizan.mac-worker',
        'ProgramArguments': [str(python), str(runtime / 'mac_worker.py')],
        'WorkingDirectory': str(workspace),
        'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 60,
        'ProcessType': 'Background',
        'StandardOutPath': str(log_dir / 'mac-worker.log'),
        'StandardErrorPath': str(log_dir / 'mac-worker.log'),
        'EnvironmentVariables': {'PATH': f'{Path.home()}/.local/bin:/usr/local/bin:/usr/bin:/bin', 'JARVIS_NUM_CTX': '4096'},
    }
    with plist.open('wb') as stream:
        plistlib.dump(data, stream)
    domain = f'gui/{os.getuid()}'
    subprocess.run(['launchctl', 'bootout', domain, str(plist)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['launchctl', 'bootstrap', domain, str(plist)], check=True)
    print('Исполнитель подключён. Напишите /macstatus в Telegram, затем отправьте тестовую задачу.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
