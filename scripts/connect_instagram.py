"""Owner-run import of a Meta-issued token; no tokens in command arguments."""
import argparse
import getpass
from account_readers import request_json,save_access,instagram_identity

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--login',choices=['facebook','instagram'],default='instagram')
    args=parser.parse_args()
    token=getpass.getpass('Meta API token (не отображается): ').strip()
    try:
        access={'access_token':token,'login':args.login}
        base,account_id=instagram_identity(access)
        request_json(base+account_id+'/insights?metric=reach&period=day',token=token)
        save_access('instagram',{**access,'username':'rashidiqmizan','user_id':account_id})
        print('Instagram @rashidiqmizan: чтение Insights подтверждено.')
    except Exception as exc:
        print('Доступ не сохранён:',type(exc).__name__);raise SystemExit(1)
