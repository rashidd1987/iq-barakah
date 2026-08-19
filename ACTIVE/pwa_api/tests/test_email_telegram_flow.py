import asyncio
import importlib.util
import os
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import asyncpg
from fastapi import HTTPException


previous_jarwas = sys.modules.get('bot_v2.services.jarwas')
previous_program = sys.modules.get('bot_v2.services.program')
jarwas_stub = types.ModuleType('bot_v2.services.jarwas')
jarwas_stub.setup_jarwas = lambda _key: None
jarwas_stub.ask_jarwas_muhasaba = lambda *_args, **_kwargs: ''
sys.modules['bot_v2.services.jarwas'] = jarwas_stub

program_stub = types.ModuleType('bot_v2.services.program')
program_stub.get_tariff_view = lambda *_args, **_kwargs: {}
sys.modules['bot_v2.services.program'] = program_stub

MODULE_PATH = Path(__file__).resolve().parents[1] / 'main.py'
SPEC = importlib.util.spec_from_file_location('pwa_api_flow', MODULE_PATH)
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)
if previous_jarwas is None:
    sys.modules.pop('bot_v2.services.jarwas', None)
else:
    sys.modules['bot_v2.services.jarwas'] = previous_jarwas
if previous_program is None:
    sys.modules.pop('bot_v2.services.program', None)
else:
    sys.modules['bot_v2.services.program'] = previous_program


class AsyncContext:
    def __init__(self, value): self.value = value
    async def __aenter__(self): return self.value
    async def __aexit__(self, *_args): return False


class MemoryDb:
    def __init__(self):
        self.users = {}
        self.email_index = {}
        self.telegram_users = set()
        self.participants = set()
        self.challenges = {}
        self.sessions = {}
        self.next_user_id = 1
        self.force_unique_on_update = False

    def acquire(self): return AsyncContext(self)
    def transaction(self): return AsyncContext(self)

    async def fetchrow(self, query, *args):
        q = ' '.join(query.split())
        if 'FROM pwa_email_otp_challenges' in q:
            return self.challenges.get(args[0])
        if 'SELECT id, email, name, tg_id FROM pwa_users WHERE email=$1' in q:
            uid = self.email_index.get(args[0]); return self.users.get(uid)
        if 'INSERT INTO pwa_users' in q and 'RETURNING id, email, name, tg_id' in q:
            name, email = args[0], args[1]
            uid = self.next_user_id; self.next_user_id += 1
            row = {'id': uid, 'name': name, 'email': email, 'tg_id': None}
            self.users[uid] = row; self.email_index[email] = uid
            return row
        if 'SELECT tg_id FROM pwa_users WHERE id=$1 FOR UPDATE' in q:
            return self.users.get(args[0])
        if 'SELECT tg_id FROM pwa_users WHERE id=$1' in q:
            return self.users.get(args[0])
        if 'SELECT id, email, tg_id FROM pwa_users WHERE id=$1' in q:
            return self.users.get(args[0])
        if 'SELECT id FROM pwa_users WHERE id=$1' in q:
            row = self.users.get(args[0]); return {'id': row['id']} if row else None
        if 'SELECT id FROM pwa_users WHERE tg_id=$1 AND id<>$2' in q:
            for row in self.users.values():
                if row['tg_id'] == args[0] and row['id'] != args[1]: return {'id': row['id']}
            return None
        if 'SELECT id FROM users WHERE id=$1' in q:
            return {'id': args[0]} if args[0] in self.telegram_users else None
        if 'SELECT id FROM participants WHERE user_id=$1' in q:
            return {'id': args[0]} if args[0] in self.participants else None
        if 'FROM pwa_tg_sessions WHERE session_id=$1 FOR UPDATE' in q:
            return self.sessions.get(args[0])
        raise AssertionError(f'unhandled fetchrow: {q}')

    async def execute(self, query, *args):
        q = ' '.join(query.split())
        if q.startswith('UPDATE pwa_email_otp_challenges SET consumed_at=NOW() WHERE email='):
            for row in self.challenges.values():
                if row['email'] == args[0] and row['consumed_at'] is None: row['consumed_at'] = datetime.utcnow()
            return 'UPDATE'
        if q.startswith('INSERT INTO pwa_email_otp_challenges'):
            cid, email, name, target, scope, code_hash, expires = args
            self.challenges[cid] = {
                'challenge_id': cid, 'email': email, 'pending_name': name,
                'target_user_id': target, 'client_scope': scope, 'code_hash': code_hash,
                'attempts': 0, 'expires_at': expires, 'consumed_at': None,
            }
            return 'INSERT'
        if q.startswith('UPDATE pwa_email_otp_challenges SET consumed_at=$2'):
            self.challenges[args[0]]['consumed_at'] = args[1]; return 'UPDATE'
        if q.startswith('UPDATE pwa_tg_sessions SET tg_id='):
            row = self.sessions.get(args[2])
            if row: row.update(tg_id=args[0], tg_name=args[1], confirmed=True)
            return 'UPDATE'
        if q.startswith('INSERT INTO pwa_tg_sessions'):
            self.sessions[args[0]] = {
                'tg_id': None, 'confirmed': False, 'target_user_id': args[1],
                'consumed_at': None, 'created_at': args[2],
            }
            return 'INSERT'
        if q.startswith('UPDATE pwa_users SET tg_id='):
            if self.force_unique_on_update:
                self.force_unique_on_update = False
                raise asyncpg.UniqueViolationError('duplicate tg_id')
            tg_id, uid = args
            if any(row['tg_id'] == tg_id and row['id'] != uid for row in self.users.values()):
                raise asyncpg.UniqueViolationError('duplicate tg_id')
            self.users[uid]['tg_id'] = tg_id; return 'UPDATE'
        if q.startswith('UPDATE pwa_tg_sessions SET consumed_at=COALESCE'):
            self.sessions[args[0]]['consumed_at'] = self.sessions[args[0]]['consumed_at'] or args[1]
            return 'UPDATE'
        raise AssertionError(f'unhandled execute: {q}')


class EmailTelegramFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = MemoryDb()
        api.db_pool = self.db
        self.env = patch.dict(os.environ, {'EMAIL_OTP_SECRET': 's' * 32}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def add_user(self, email, tg_id=None):
        uid = self.db.next_user_id; self.db.next_user_id += 1
        self.db.users[uid] = {'id': uid, 'name': 'User', 'email': email, 'tg_id': tg_id}
        self.db.email_index[email] = uid
        return uid

    async def test_new_email_otp_returns_telegram_required(self):
        delivered = {}
        async def capture(email, code): delivered.update(email=email, code=code)
        with patch.object(api, '_deliver_email_otp', capture), patch.object(api.secrets, 'token_urlsafe', return_value='challenge'), patch.object(api.secrets, 'randbelow', return_value=123456):
            requested = await api.request_email_otp(api.EmailOtpRequestReq(email='NEW@example.com', name='New', client_scope='mobile'), None)
            result = await api.verify_email_otp(api.EmailOtpVerifyReq(challenge_id=requested['challenge_id'], code=delivered['code']))
        self.assertEqual(result['status'], 'telegram_required')
        self.assertTrue(result['access_token'])

    async def test_link_init_confirm_check_returns_mobile_token(self):
        uid = self.add_user('one@example.com')
        self.db.telegram_users.add(101); self.db.participants.add(101)
        with patch.object(api.secrets, 'token_urlsafe', return_value='session'):
            created = await api.telegram_link_init(uid)
        await api.tg_confirm(api.TgConfirmReq(session_id='session', tg_id=101, tg_name='TG', secret=api.BOT_SECRET))
        result = await api.telegram_link_check(created['session_id'], uid)
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['access_token'])

    async def test_tg_confirm_requires_configured_bot_secret(self):
        uid = self.add_user('secret@example.com')
        self.db.sessions['session'] = {
            'tg_id': None, 'confirmed': False, 'target_user_id': uid,
            'consumed_at': None, 'created_at': datetime.utcnow(),
        }
        with self.assertRaises(HTTPException) as raised:
            await api.tg_confirm(api.TgConfirmReq(
                session_id='session', tg_id=101, tg_name='TG', secret='wrong-secret',
            ))
        self.assertEqual(raised.exception.status_code, 403)
        self.assertFalse(self.db.sessions['session']['confirmed'])

        await api.tg_confirm(api.TgConfirmReq(
            session_id='session', tg_id=101, tg_name='TG', secret=api.BOT_SECRET,
        ))
        self.assertTrue(self.db.sessions['session']['confirmed'])

    async def test_foreign_owner_cannot_check_session(self):
        owner = self.add_user('owner@example.com'); foreign = self.add_user('foreign@example.com')
        self.db.sessions['s'] = {'tg_id': 1, 'confirmed': True, 'target_user_id': owner, 'consumed_at': None, 'created_at': datetime.utcnow()}
        with self.assertRaises(HTTPException) as raised: await api.telegram_link_check('s', foreign)
        self.assertEqual(raised.exception.status_code, 404)

    async def test_expired_session_is_gone(self):
        uid = self.add_user('expired@example.com')
        self.db.sessions['s'] = {'tg_id': 1, 'confirmed': True, 'target_user_id': uid, 'consumed_at': None, 'created_at': datetime.utcnow() - timedelta(minutes=11)}
        with self.assertRaises(HTTPException) as raised: await api.telegram_link_check('s', uid)
        self.assertEqual(raised.exception.status_code, 410)

    async def test_telegram_linked_elsewhere_is_conflict_without_mutation(self):
        owner = self.add_user('owner@example.com'); other = self.add_user('other@example.com', 77)
        self.db.telegram_users.add(77)
        self.db.sessions['s'] = {'tg_id': 77, 'confirmed': True, 'target_user_id': owner, 'consumed_at': None, 'created_at': datetime.utcnow()}
        with self.assertRaises(HTTPException) as raised: await api.telegram_link_check('s', owner)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIsNone(self.db.users[owner]['tg_id']); self.assertEqual(self.db.users[other]['tg_id'], 77)

    async def test_unique_race_becomes_controlled_conflict(self):
        uid = self.add_user('race@example.com'); self.db.telegram_users.add(88)
        self.db.sessions['s'] = {'tg_id': 88, 'confirmed': True, 'target_user_id': uid, 'consumed_at': None, 'created_at': datetime.utcnow()}
        self.db.force_unique_on_update = True
        with self.assertRaises(HTTPException) as raised: await api.telegram_link_check('s', uid)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertIsNone(self.db.users[uid]['tg_id'])

    async def test_two_concurrent_link_checks_have_one_winner(self):
        first_user = self.add_user('first@example.com')
        second_user = self.add_user('second@example.com')
        self.db.telegram_users.add(89)
        self.db.participants.add(89)
        now = datetime.utcnow()
        self.db.sessions['first'] = {
            'tg_id': 89, 'confirmed': True, 'target_user_id': first_user,
            'consumed_at': None, 'created_at': now,
        }
        self.db.sessions['second'] = {
            'tg_id': 89, 'confirmed': True, 'target_user_id': second_user,
            'consumed_at': None, 'created_at': now,
        }

        results = await asyncio.gather(
            api.telegram_link_check('first', first_user),
            api.telegram_link_check('second', second_user),
            return_exceptions=True,
        )

        successes = [result for result in results if isinstance(result, dict)]
        conflicts = [
            result for result in results
            if isinstance(result, HTTPException) and result.status_code == 409
        ]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(
            sum(row['tg_id'] == 89 for row in self.db.users.values()),
            1,
        )

    async def test_linked_without_participant_then_activation_becomes_ok(self):
        uid = self.add_user('linked@example.com', 99)
        first = await api.mobile_session(('pwa', uid))
        self.assertEqual(first['status'], 'activation_required')
        self.db.participants.add(99)
        second = await api.mobile_session(('pwa', uid))
        self.assertEqual(second['status'], 'ok')

    async def test_own_confirmed_session_is_idempotent(self):
        uid = self.add_user('same@example.com', 111)
        self.db.telegram_users.add(111); self.db.participants.add(111)
        self.db.sessions['s'] = {'tg_id': 111, 'confirmed': True, 'target_user_id': uid, 'consumed_at': datetime.utcnow(), 'created_at': datetime.utcnow()}
        first = await api.telegram_link_check('s', uid)
        second = await api.telegram_link_check('s', uid)
        self.assertEqual(first['status'], 'ok'); self.assertEqual(second['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
