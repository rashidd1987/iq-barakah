"""Owner-run import of a Meta-issued token. Never accepts tokens on command line."""
import getpass
from account_readers import request_json,save_access

if __name__=='__main__':
    token=getpass.getpass('Instagram API token (не отображается): ').strip()
    try:
        profile=request_json('https://graph.instagram.com/v27.0/me?fields=user_id,username',token=token)
        if profile.get('username','').casefold()!='rashidiqmizan':
            raise ValueError('wrong account')
        account_id=str(profile.get('user_id',''))
        if not account_id.isdigit():raise ValueError('invalid account')
        # Verify the specific capability before storing credentials.
        request_json('https://graph.instagram.com/v27.0/'+account_id+'/insights?metric=reach&period=day',token=token)
        save_access('instagram',{'access_token':token,'username':'rashidiqmizan','user_id':account_id})
        print('Instagram @rashidiqmizan: чтение Insights подтверждено.')
    except Exception as exc:
        print('Доступ не сохранён:',type(exc).__name__);raise SystemExit(1)
