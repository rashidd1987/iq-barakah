"""Narrow account readers. Credentials never enter prompts or process arguments."""
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode, urlsplit

ROOT = Path.home() / '.openjarvis' / 'account-access'
GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'


def request_json(url, *, token=None, form=None):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'oauth2.googleapis.com', 'gmail.googleapis.com', 'graph.instagram.com'} or parsed.username or parsed.port:
        raise ValueError('unapproved account endpoint')
    if form is not None and url != 'https://oauth2.googleapis.com/token':
        raise ValueError('account writes are disabled')
    def quoted(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'
    settings = ['url = ' + quoted(url)]
    if token:
        if any(c in token for c in '\r\n'):
            raise ValueError('invalid token')
        settings.append('header = ' + quoted('Authorization: Bearer ' + token))
    if form is not None:
        settings.append('request = "POST"')
        settings += ['data-urlencode = ' + quoted(k + '=' + v) for k, v in form.items()]
    response = subprocess.run(['/usr/bin/curl', '--disable', '--config', '-', '--silent', '--show-error',
        '--fail', '--proto', '=https', '--max-redirs', '0', '--ipv4', '--http1.1',
        '--connect-timeout', '8', '--max-time', '25', '--max-filesize', '1000000'],
        input='\n'.join(settings)+'\n', text=True, capture_output=True, timeout=30)
    if response.returncode:
        raise OSError('Account API unavailable or authorization rejected')
    payload = json.loads(response.stdout)
    if not isinstance(payload, dict) or 'error' in payload:
        raise ValueError('Account API returned an error')
    return payload


def load_access(name):
    p = ROOT / (name + '.json')
    if p.is_symlink() or not p.exists() or p.stat().st_mode & 0o077:
        raise ValueError('Account access has not been configured securely')
    return json.loads(p.read_text())


def save_access(name, data):
    ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
    ROOT.chmod(0o700)
    from mac_worker import atomic_json
    atomic_json(ROOT / (name + '.json'), data)


def gmail_report():
    access = load_access('gmail')
    if set(access.get('scope','').split()) != {GMAIL_SCOPE}:
        raise ValueError('Only Gmail readonly authorization is accepted')
    tokens = request_json('https://oauth2.googleapis.com/token', form={
        'grant_type':'refresh_token', 'refresh_token':access['refresh_token'],
        'client_id':access['client_id'], 'client_secret':access['client_secret']})
    token = tokens['access_token']
    base = 'https://gmail.googleapis.com/gmail/v1/users/me/'
    profile = request_json(base+'profile', token=token)
    if profile.get('emailAddress','').casefold() != access['email'].casefold():
        raise ValueError('Wrong Gmail account')
    listing = request_json(base+'messages?'+urlencode({'q':'in:inbox is:unread','maxResults':10}),token=token)
    lines = ['Gmail: непрочитанные письма во входящих (не более 10).']
    for item in listing.get('messages',[]):
        message_id = item.get('id','')
        if not re.fullmatch('[a-fA-F0-9]+',message_id):
            raise ValueError('Invalid message id')
        message = request_json(base+'messages/'+message_id+'?'+urlencode([
            ('format','metadata'),('metadataHeaders','From'),('metadataHeaders','Subject'),('metadataHeaders','Date')]),token=token)
        headers = {h['name'].casefold():h.get('value','') for h in message.get('payload',{}).get('headers',[])}
        subject = headers.get('subject','Без темы')
        if re.search(r'verif|security|sign.?in|парол|подтверж|вход|проверочн|код',subject,re.I):
            subject = '[Уведомление безопасности — содержание скрыто]'
        subject = re.sub(r'\b\d{4,8}\b','[код скрыт]',subject)
        lines.append('- '+subject[:200]+' | '+headers.get('from','')[:150])
    if not listing.get('messages'):
        lines.append('Непрочитанных писем во входящих нет.')
    lines.append('Письма не изменялись. Показаны отправители и темы; тела писем и вложения не читались.')
    return '\n'.join(lines)


def instagram_report():
    from datetime import datetime,timedelta,timezone
    access=load_access('instagram')
    token=access['access_token']
    profile=request_json('https://graph.instagram.com/v27.0/me?fields=user_id,username',token=token)
    if profile.get('username','').casefold() != 'rashidiqmizan':
        raise ValueError('Wrong Instagram account')
    account_id=str(profile.get('user_id',''))
    if not account_id.isdigit():
        raise ValueError('Invalid Instagram account id')
    today=datetime.now(timezone.utc).date()
    query=urlencode({'metric':'reach','period':'day','since':str(today-timedelta(days=7)),'until':str(today)})
    metrics=request_json('https://graph.instagram.com/v27.0/'+account_id+'/insights?'+query,token=token)
    lines=['Instagram @rashidiqmizan: дневной охват за последние 7 завершённых дней (UTC).']
    rows=0
    for metric in metrics.get('data',[]):
        if metric.get('name') != 'reach':continue
        for value in metric.get('values',[])[:8]:
            lines.append(str(value.get('end_time',''))[:10]+': '+str(value.get('value','нет данных')));rows+=1
    if not rows:lines.append('API не вернул дневные значения охвата. Нули не подставлялись.')
    lines.append('Это дневные показатели, не уникальный охват за всю неделю. Публикации и сообщения не изменялись.')
    return '\n'.join(lines)


def account_report(task):
    text=task.casefold()
    gmail=any(word in text for word in ('gmail','почт','письм'))
    instagram=any(word in text for word in ('instagram','инстаграм','инстагр'))
    if not (gmail or instagram):return None
    if any(word in text for word in ('отправь','удали','опубликуй','ответь')):
        return {'status':'failed','result':'Для почты и Instagram подключено только чтение. Отправка, удаление и публикация недоступны.'}
    if not any(word in text for word in ('провер','прочит','покаж','статист','охват','непрочит','входящ','check','read','insight')):
        return None
    try:
        sections=[]
        if gmail:sections.append(gmail_report())
        if instagram:sections.append(instagram_report())
        return {'status':'done','result':'\n\n'.join(sections)[:14000]}
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):
        return {'status':'failed','result':'Доступ к аккаунту ещё не подтверждён или провайдер недоступен. Нужна настройка Gmail readonly / Instagram Insights на Mac. Данные не выдумывались.'}
