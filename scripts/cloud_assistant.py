"""Server account reads only; never imports a model, shell tools or Mac apps."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from account_readers import account_report
from mac_worker import atomic_json


def execute(task, workspace=None):
    from project_report import wants_project_report, report
    if wants_project_report(task):
        return report(Path(workspace) if workspace else Path.home() / 'workspace')
    result = account_report(task)
    if result is None:
        return {'status': 'failed', 'result': 'Сервер выполняет только проверку Gmail и статистики Instagram. Другие поручения остаются на Mac.'}
    if result['status'] == 'done':
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        result['result'] += '\n\nПроверено сервером: ' + stamp + '. Mac не использовался.'
    return result


if __name__ == '__main__':
    request_path, result_path = map(Path, sys.argv[1:3])
    request = json.loads(request_path.read_text())
    try:
        result = execute(request['task'], request.get('workspace'))
    except Exception:
        result = {'status': 'failed', 'result': 'Сервер не завершил проверку аккаунта. Данные не выдумывались.'}
    atomic_json(result_path, result)
