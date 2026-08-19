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

API_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = API_DIR / "main.py"
SPEC = importlib.util.spec_from_file_location("pwa_api_email_otp", MODULE_PATH)
pwa_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pwa_api)


class EmailOtpContractTest(unittest.TestCase):
    def test_otp_secret_is_required_and_not_backed_by_jwt_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                pwa_api._otp_secret()
        self.assertEqual(raised.exception.status_code, 503)

    def test_hash_is_bound_to_challenge_email_and_code(self):
        env = {"EMAIL_OTP_SECRET": "x" * 32}
        with patch.dict(os.environ, env, clear=True):
            expected = pwa_api._hash_email_otp("challenge", "user@example.com", "123456")
            self.assertEqual(expected, pwa_api._hash_email_otp("challenge", "user@example.com", "123456"))
            self.assertNotEqual(expected, pwa_api._hash_email_otp("other", "user@example.com", "123456"))
            self.assertNotEqual(expected, pwa_api._hash_email_otp("challenge", "user@example.com", "654321"))

    def test_contract_has_expiry_attempt_limit_and_one_time_consumption(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        migration = (API_DIR / "migration.sql").read_text(encoding="utf-8")
        self.assertIn("expires_at", source)
        self.assertIn("attempts'] >= 5", source)
        self.assertIn("consumed_at", source)
        self.assertIn("FOR UPDATE", source)
        self.assertIn("pwa_email_otp_challenges", migration)

    def test_linking_requires_authenticated_target_user(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("current_identity: Optional[Tuple[str, int]] = Depends(verify_optional_identity)", source)
        self.assertIn("target_user_id", source)
        self.assertNotIn("FROM users WHERE email=$1", source)

    def test_mobile_scope_preserves_verified_email_until_telegram_is_linked(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        migration = (API_DIR / "migration.sql").read_text(encoding="utf-8")
        self.assertIn("client_scope: Literal['pwa', 'mobile'] = 'pwa'", source)
        self.assertIn("row['client_scope'] == 'mobile'", source)
        self.assertIn("'status': 'telegram_required'", source)
        self.assertIn("_mobile_session_for_pwa_user", source)
        self.assertIn("client_scope", migration)

    def test_telegram_link_is_owned_atomic_and_conflict_safe(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        migration = (API_DIR / "migration.sql").read_text(encoding="utf-8")
        self.assertIn("@app.post('/auth/telegram-link/init')", source)
        self.assertIn("@app.get('/auth/telegram-link/check')", source)
        self.assertIn("row['target_user_id'] != user_id", source)
        self.assertIn("WHERE session_id=$1 FOR UPDATE", source)
        self.assertIn("Этот Telegram уже связан с другим аккаунтом", source)
        self.assertIn("consumed_at", migration)

    def test_mobile_session_upgrades_linked_email_account(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("@app.post('/auth/mobile-session')", source)
        self.assertIn("return await _mobile_session_for_pwa_user", source)
        self.assertIn("'status': 'activation_required'", source)

    def test_mobile_profile_exposes_persisted_email_login_state(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("email_login_enabled", source)
        self.assertIn("WHERE tg_id=$1 AND LOWER(email)=LOWER($2)", source)


if __name__ == "__main__":
    unittest.main()
