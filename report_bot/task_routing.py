"""Pure routing shared by the bot and its narrow server executor."""
import os


def is_account_task(task):
    text = task.casefold()
    account = any(word in text for word in ('gmail', 'почт', 'письм', 'instagram', 'инстаграм', 'инстагр'))
    intent = any(word in text for word in (
        'провер', 'прочит', 'покаж', 'статист', 'охват', 'непрочит', 'входящ',
        'check', 'read', 'insight', 'отчет', 'отчёт', 'сводк', 'глянь', 'посмотр',
        'отправь', 'удали', 'опубликуй', 'ответь'))
    return account and intent


def is_project_task(task):
    import re
    text = re.sub(r'[\s_-]+', '', task.casefold())
    project = any(name in text for name in ('iqbarak', 'айкьюбарак', 'икьюбарак', 'iqбарак', 'айкюбарак'))
    return project and any(word in text for word in ('провер', 'аудит', 'отч', 'состояни', 'ошиб', 'check', 'audit', 'report'))


def task_target(task):
    if os.environ.get('CLOUD_READERS_ENABLED', '1') == '1' and (is_account_task(task) or is_project_task(task)):
        return 'cloud'
    return 'mac'


def executor_label(job):
    return 'Сервер' if job.get('target') == 'cloud' else 'Mac'
