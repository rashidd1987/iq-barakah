"""Outbound-only Mizan worker. Configuration and results stay outside Git."""

import fcntl
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path.home() / '.openjarvis'
logger = logging.getLogger('mizan.mac')


def atomic_json(path: Path, value):
    temp = path.with_suffix('.tmp')
    with temp.open('w') as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def api(config, route: str, body=None):
    validate_config(config)
    if not route.startswith('/mac-worker/') or any(c in route for c in ('\n', '\r', '?', '#')):
        raise ValueError('invalid worker route')
    # macOS SecureTransport works on networks where Python TLS handshakes stall.
    # Curl config is supplied via stdin: secrets never appear in process arguments.
    def quoted(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'
    settings = [
        'url = ' + quoted(config['reports_url'].rstrip('/') + route),
        'header = ' + quoted('Authorization: Bearer ' + config['secret']),
        'header = "Content-Type: application/json"',
    ]
    if body is not None:
        settings += ['request = "POST"', 'data = ' + quoted(json.dumps(body))]
    response = subprocess.run(
        ['/usr/bin/curl', '--disable', '--config', '-', '--silent', '--show-error',
         '--fail', '--proto', '=https', '--proto-redir', '=https', '--max-redirs', '0',
         '--ipv4', '--http1.1', '--retry', '2', '--retry-all-errors', '--retry-delay', '1',
         '--connect-timeout', '8', '--max-time', '20', '--max-filesize', '100000'],
        input='\n'.join(settings) + '\n', capture_output=True, text=True, timeout=70,
    )
    if response.returncode:
        raise OSError('Reports HTTPS transport failed')
    return json.loads(response.stdout)


def validate_config(config):
    parsed = urlsplit(config['reports_url'])
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('reports_url must be an HTTPS origin')
    if len(config['secret']) < 32:
        raise ValueError('worker secret is too short')
    workspace = Path(config['workspace']).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError('workspace does not exist')


def process(config, job, state_dir):
    # IDs originate from the server, but never trust them as filesystem paths.
    import re
    if not re.fullmatch('[a-f0-9]{12}', job['id']):
        raise ValueError('invalid job id')
    folder = state_dir / job['id']
    folder.mkdir(mode=0o700, exist_ok=True)
    result_path = folder / 'result.json'
    started = folder / 'started'
    request_path = folder / 'request.json'
    if not started.exists() and not result_path.exists():
        atomic_json(request_path, {'task': job['task'], 'workspace': config['workspace']})
        started.touch(mode=0o600)
        try:
            subprocess.run([sys.executable, str(Path(__file__).with_name('mac_assistant.py')),
                            str(request_path), str(result_path)], timeout=900,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except (subprocess.SubprocessError, OSError):
            atomic_json(result_path, {'status': 'unknown', 'result': 'Выполнение прервано. Часть файлов могла сохраниться. Проверьте рабочую папку Mac; автоматический повтор отключён.'})
    if not result_path.exists():
        atomic_json(result_path, {'status': 'unknown', 'result': 'Mac перезапустился во время задачи. Проверьте рабочую папку; автоматический повтор отключён.'})
    try:
        result = json.loads(result_path.read_text())
        if (not isinstance(result, dict) or result.get('status') not in {'done', 'failed', 'unknown'}
                or not isinstance(result.get('result'), str) or not 1 <= len(result['result']) <= 16000):
            raise ValueError('invalid local result')
    except (ValueError, TypeError):
        result_path.replace(folder / 'result.corrupt')
        result = {'status': 'unknown', 'result': 'Сохранённый результат задачи повреждён. Проверьте рабочую папку; повторное выполнение отключено.'}
        atomic_json(result_path, result)
    if job.get('voice_reply') and 'voice' not in result and not result.get('voice_error'):
        try:
            from spoken_result import render_voice
            result['voice'] = render_voice(result['result'])
        except (OSError, ValueError, subprocess.SubprocessError):
            result['voice_error'] = True
        atomic_json(result_path, result)
    api(config, f'/mac-worker/jobs/{job["id"]}/result', {**result, 'claim_token': job['claim_token']})
    logger.info('Reported job %s (%s)', job['id'], result['status'])


def main():
    os.umask(0o077)
    config_path = ROOT / 'mac-worker.json'
    if not config_path.exists():
        logger.error('Not paired: configure ~/.openjarvis/mac-worker.json')
        return 2
    if config_path.stat().st_mode & 0o077:
        logger.error('Worker config must have mode 600')
        return 2
    config = json.loads(config_path.read_text())
    validate_config(config)
    state_dir = ROOT / 'mac-jobs'
    state_dir.mkdir(mode=0o700, exist_ok=True)
    lock = (ROOT / 'mac-worker.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.error('Another Mac worker is running')
        return 2
    failures = 0
    while True:
        try:
            recovered = api(config, '/mac-worker/running')['jobs']
            for job in recovered:
                process(config, job, state_dir)
            job = api(config, '/mac-worker/claim', {})['job']
            if job:
                process(config, job, state_dir)
            failures = 0
        except Exception:
            failures = min(failures + 1, 5)
            logger.warning('Reports connection unavailable; retrying without repeating completed work')
        time.sleep(min(15 * 2 ** failures, 120))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    raise SystemExit(main())
