import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


jarwas_stub = types.ModuleType("bot_v2.services.jarwas")
jarwas_stub.setup_jarwas = lambda _api_key: None

async def _ask_jarwas_muhasaba_stub(*_args, **_kwargs):
    return ""

jarwas_stub.ask_jarwas_muhasaba = _ask_jarwas_muhasaba_stub
sys.modules["bot_v2.services.jarwas"] = jarwas_stub

MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
SPEC = importlib.util.spec_from_file_location("pwa_api_account_deletion", MODULE_PATH)
pwa_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pwa_api)


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Transaction:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.rolled_back = exc_type is not None
        self.committed = exc_type is None
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


class _DeleteConnection:
    def __init__(self, user_exists=True, pwa_user_exists=True, fail_on=None):
        self.user_exists = user_exists
        self.pwa_user_exists = pwa_user_exists
        self.fail_on = fail_on
        self.executed = []
        self.tx = _Transaction()

    def transaction(self):
        return self.tx

    async def fetchrow(self, query, user_id):
        if "FROM users" in query:
            return {"id": user_id} if self.user_exists else None
        if "FROM pwa_users" in query:
            return {"id": 77} if self.pwa_user_exists else None
        raise AssertionError(f"Unexpected fetch: {query}")

    async def execute(self, query, *args):
        if self.fail_on and self.fail_on in query:
            raise RuntimeError("simulated database failure")
        self.executed.append((query, args))
        return "OK"


class AccountDeletionContractTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_pool = pwa_api.db_pool

    async def asyncTearDown(self):
        pwa_api.db_pool = self.original_pool

    async def test_requires_exact_confirmation(self):
        with self.assertRaises(HTTPException) as raised:
            await pwa_api.mobile_delete_account(
                pwa_api.MobileAccountDeleteReq(confirmation="удалить"),
                tg_id=123,
            )
        self.assertEqual(raised.exception.status_code, 400)

    async def test_protected_account_is_rejected_before_database_access(self):
        with patch.dict(os.environ, {"ACCOUNT_DELETION_PROTECTED_IDS": "123,456"}):
            with self.assertRaises(HTTPException) as raised:
                await pwa_api.mobile_delete_account(
                    pwa_api.MobileAccountDeleteReq(confirmation="УДАЛИТЬ"),
                    tg_id=123,
                )
        self.assertEqual(raised.exception.status_code, 403)

    async def test_deletes_personal_data_and_anonymises_payments_atomically(self):
        connection = _DeleteConnection()
        pwa_api.db_pool = _Pool(connection)

        result = await pwa_api.mobile_delete_account(
            pwa_api.MobileAccountDeleteReq(confirmation=" УДАЛИТЬ "),
            tg_id=123,
        )

        self.assertEqual(result, {"ok": True, "already_deleted": False})
        self.assertTrue(connection.tx.committed)
        sql = "\n".join(query for query, _ in connection.executed)
        self.assertIn("UPDATE bot_payments SET user_id=$1, email_used=NULL", sql)
        self.assertIn("UPDATE users SET referred_by=NULL", sql)
        self.assertIn("DELETE FROM push_tokens", sql)
        self.assertIn("DELETE FROM pwa_tg_sessions", sql)
        self.assertIn("DELETE FROM pairs", sql)
        self.assertIn("DELETE FROM task_completions", sql)
        self.assertIn("DELETE FROM wheel_records", sql)
        self.assertIn("DELETE FROM tracker_records", sql)
        self.assertIn("DELETE FROM week_acks", sql)
        self.assertIn("DELETE FROM muhasaba_logs", sql)
        self.assertIn("DELETE FROM diag_results", sql)
        self.assertIn("DELETE FROM participants", sql)
        self.assertIn("DELETE FROM pwa_users", sql)
        self.assertTrue(sql.rstrip().endswith("DELETE FROM users WHERE id=$1"))

    async def test_missing_account_is_idempotent(self):
        connection = _DeleteConnection(user_exists=False)
        pwa_api.db_pool = _Pool(connection)

        result = await pwa_api.mobile_delete_account(
            pwa_api.MobileAccountDeleteReq(confirmation="УДАЛИТЬ"),
            tg_id=123,
        )

        self.assertEqual(result, {"ok": True, "already_deleted": True})
        self.assertEqual(connection.executed, [])
        self.assertTrue(connection.tx.committed)

    async def test_database_failure_rolls_back_the_transaction(self):
        connection = _DeleteConnection(fail_on="DELETE FROM participants")
        pwa_api.db_pool = _Pool(connection)

        with self.assertRaises(RuntimeError):
            await pwa_api.mobile_delete_account(
                pwa_api.MobileAccountDeleteReq(confirmation="УДАЛИТЬ"),
                tg_id=123,
            )

        self.assertTrue(connection.tx.rolled_back)
        self.assertFalse(connection.tx.committed)


if __name__ == "__main__":
    unittest.main()
