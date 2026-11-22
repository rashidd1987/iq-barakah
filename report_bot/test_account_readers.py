import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('account_readers',Path(__file__).parents[1]/'scripts/account_readers.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class AccountReaderTests(unittest.TestCase):
    def test_endpoints_cannot_be_redirected_or_write_accounts(self):
        for url in ['http://gmail.googleapis.com/','https://evil.example/','https://token@gmail.googleapis.com/']:
            with self.assertRaises(ValueError):m.request_json(url)
        with self.assertRaises(ValueError):m.request_json('https://gmail.googleapis.com/',form={'x':'y'})

    def test_tokens_stay_off_command_line_and_tls_stays_on(self):
        with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{}')) as run:
            m.request_json('https://graph.instagram.com/v27.0/me',token='test-secret')
        self.assertNotIn('test-secret',' '.join(run.call_args.args[0]))
        self.assertIn('test-secret',run.call_args.kwargs['input'])
        self.assertNotIn('--location',run.call_args.args[0])
        self.assertNotIn('--insecure',run.call_args.args[0])

    def test_unconfigured_or_weakly_protected_accounts_fail_closed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(m,'ROOT',Path(d)):
            result=m.account_report('Проверь почту Gmail')
            self.assertEqual(result['status'],'failed')
            p=Path(d)/'gmail.json';p.write_text('{}');p.chmod(0o644)
            with self.assertRaises(ValueError):m.load_access('gmail')

    def test_write_requests_never_call_api(self):
        with patch.object(m,'request_json') as api:
            self.assertEqual(m.account_report('Отправь письмо Gmail')['status'],'failed')
            self.assertEqual(m.account_report('Опубликуй Instagram пост')['status'],'failed')
            api.assert_not_called()
        self.assertIsNone(m.account_report('Напиши черновик поста Instagram'))
        self.assertIsNone(m.account_report('Проверь проект IQ Barakah'))

    def test_broad_gmail_scope_is_rejected(self):
        with patch.object(m,'load_access',return_value={'scope':'https://www.googleapis.com/auth/gmail.modify'}),patch.object(m,'request_json') as api:
            with self.assertRaises(ValueError):m.gmail_report()
            api.assert_not_called()

    def test_gmail_verifies_identity_and_hides_security_subjects(self):
        access=dict(scope=m.GMAIL_SCOPE,refresh_token='refresh',client_id='id',client_secret='secret',email='rashidd1987@gmail.com')
        payloads=[{'access_token':'access'},{'emailAddress':'rashidd1987@gmail.com'},
                  {'messages':[{'id':'abc123'}]}, {'payload':{'headers':[{'name':'Subject','value':'Ваш код 123456'},{'name':'From','value':'security@example.com'}]}}]
        with patch.object(m,'load_access',return_value=access),patch.object(m,'request_json',side_effect=payloads):
            report=m.gmail_report()
            self.assertNotIn('123456',report)
            self.assertIn('скрыто',report)
        payloads=[{'access_token':'access'},{'emailAddress':'other@example.com'}]
        with patch.object(m,'load_access',return_value=access),patch.object(m,'request_json',side_effect=payloads):
            with self.assertRaises(ValueError):m.gmail_report()

    def test_instagram_does_not_sum_daily_unique_reach(self):
        payloads=[{'username':'rashidiqmizan','user_id':'123'}, {'data':[{'name':'reach','values':[{'end_time':'2026-11-21','value':100},{'end_time':'2026-11-22','value':100}]}]}]
        with patch.object(m,'load_access',return_value={'access_token':'test','login':'instagram'}),patch.object(m,'request_json',side_effect=payloads):
            report=m.instagram_report()
            self.assertNotIn('200',report)
            self.assertIn('не уникальный охват',report)

    def test_facebook_insights_only_uses_authorized_matching_instagram(self):
        pages={'data':[{'instagram_business_account':{'id':'123','username':'rashidiqmizan'}}]}
        with patch.object(m,'request_json',return_value=pages):
            self.assertEqual(m.instagram_identity({'login':'facebook','access_token':'test'}),('https://graph.facebook.com/v27.0/','123'))
        with patch.object(m,'request_json',return_value={'data':[]}):
            with self.assertRaises(ValueError):m.instagram_identity({'login':'facebook','access_token':'test'})
