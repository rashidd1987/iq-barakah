import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
SPEC = importlib.util.spec_from_file_location("pwa_api_wheel_contract", MODULE_PATH)
pwa_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pwa_api)


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


class _WheelConnection:
    def __init__(self):
        self.saved = None

    async def fetchrow(self, query, user_id):
        assert "FROM wheel_records" in query
        assert user_id == 140700248
        return {
            "scores": {"Вера (Иман)": 8, "Намаз": 7},
            "created_at": datetime(2026, 7, 28, 4, 24),
        }

    async def execute(self, query, user_id, scores, created_at):
        assert "INSERT INTO wheel_records" in query
        assert user_id == 140700248
        self.saved = scores


class WheelSyncContractTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_pool = pwa_api.db_pool
        self.connection = _WheelConnection()
        pwa_api.db_pool = _Pool(self.connection)

    async def asyncTearDown(self):
        pwa_api.db_pool = self.original_pool

    async def test_mobile_and_miniapp_read_the_same_wheel_record(self):
        mobile = await pwa_api.mobile_get_wheel(140700248)
        with patch.object(
            pwa_api,
            "_verify_telegram_init_data",
            return_value={"user": '{"id": 140700248}'},
        ):
            miniapp = await pwa_api.miniapp_get_wheel(
                pwa_api.MiniappWheelReq(init_data="valid")
            )

        self.assertEqual(miniapp, mobile)

    async def test_miniapp_saves_to_shared_wheel_records(self):
        scores = {"Вера (Иман)": 9, "Намаз": 8}
        with patch.object(
            pwa_api,
            "_verify_telegram_init_data",
            return_value={"user": '{"id": 140700248}'},
        ):
            result = await pwa_api.miniapp_save_wheel(
                pwa_api.MiniappWheelSaveReq(init_data="valid", scores=scores)
            )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(self.connection.saved, scores)


if __name__ == "__main__":
    unittest.main()
