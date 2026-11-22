"""User-run Desktop OAuth with PKCE; only Gmail readonly is requested."""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import time
from urllib.parse import parse_qs,urlsplit,urlencode
from account_readers import GMAIL_SCOPE,request_json,save_access


def connect(client_file):
    client=json.loads(Path(client_file).expanduser().read_text()).get('installed',{})
    if not client.get('client_id') or not client.get('client_secret'):
        raise ValueError('Нужен JSON OAuth-клиента типа Desktop app')
    verifier=secrets.token_urlsafe(64)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    state=secrets.token_urlsafe(32)
    received={}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query=parse_qs(urlsplit(self.path).query)
            valid=(urlsplit(self.path).path=='/callback' and query.get('state')==[state] and len(query.get('code',[]))==1)
            if valid:received['code']=query['code'][0]
            self.send_response(200 if valid else 400);self.end_headers()
            self.wfile.write(b'Authorization received. Return to the Terminal.' if valid else b'Invalid callback.')
        def log_message(self,*args):pass
    with HTTPServer(('127.0.0.1',0),Handler) as server:
        redirect=f'http://127.0.0.1:{server.server_port}/callback'
        auth='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({
            'client_id':client['client_id'],'redirect_uri':redirect,'response_type':'code',
            'scope':GMAIL_SCOPE,'access_type':'offline','prompt':'consent','include_granted_scopes':'false',
            'state':state,'code_challenge':challenge,'code_challenge_method':'S256'})
        print('Откройте эту ссылку в Chrome и сами подтвердите чтение Gmail:\n'+auth,flush=True)
        server.timeout=1;deadline=time.monotonic()+600
        while not received and time.monotonic()<deadline:server.handle_request()
    if not received:raise ValueError('Срок ожидания истёк; доступ не сохранён')
    tokens=request_json('https://oauth2.googleapis.com/token',form={
        'grant_type':'authorization_code','code':received['code'],'client_id':client['client_id'],
        'client_secret':client['client_secret'],'redirect_uri':redirect,'code_verifier':verifier})
    if set(tokens.get('scope','').split()) != {GMAIL_SCOPE} or not tokens.get('refresh_token'):
        raise ValueError('Не получено отдельное разрешение Gmail readonly')
    profile=request_json('https://gmail.googleapis.com/gmail/v1/users/me/profile',token=tokens['access_token'])
    if profile.get('emailAddress','').casefold() != 'rashidd1987@gmail.com':
        raise ValueError('Выбран другой Gmail-аккаунт; доступ не сохранён')
    save_access('gmail',{'client_id':client['client_id'],'client_secret':client['client_secret'],
        'refresh_token':tokens['refresh_token'],'scope':GMAIL_SCOPE,'email':profile['emailAddress']})
    print('Gmail readonly подключён. Токены не выводились.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--client',required=True)
    args=parser.parse_args()
    try:connect(args.client)
    except Exception as exc:print('Настройка не завершена:',type(exc).__name__);raise SystemExit(1)
