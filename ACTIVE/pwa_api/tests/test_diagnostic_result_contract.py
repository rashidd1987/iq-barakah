import importlib.util
import sys
import types
import unittest
from pathlib import Path


jarwas_stub = types.ModuleType("bot_v2.services.jarwas")
jarwas_stub.setup_jarwas = lambda _api_key: None

async def _ask_jarwas_muhasaba_stub(*_args, **_kwargs):
    return ""

jarwas_stub.ask_jarwas_muhasaba = _ask_jarwas_muhasaba_stub
sys.modules["bot_v2.services.jarwas"] = jarwas_stub

MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
SPEC = importlib.util.spec_from_file_location("pwa_api_diagnostic_contract", MODULE_PATH)
pwa_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pwa_api)


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


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


class _DiagnosticConnection:
    def __init__(self):
        self.inserted_diag = None
        self.updated_participant = None

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, query, user_id):
        assert user_id == 140700248
        assert "FROM participants" in query
        return {"id": 77, "level": "А", "vakt_level": "I"}

    async def execute(self, query, *args):
        if "INSERT INTO diag_results" in query:
            self.inserted_diag = args[:4]
            return "INSERT 0 1"
        if "UPDATE participants SET vakt_level" in query:
            self.updated_participant = args
            return "UPDATE 1"
        raise AssertionError(f"Unexpected query: {query}")


class DiagnosticResultContractTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_pool = pwa_api.db_pool
        self.connection = _DiagnosticConnection()
        pwa_api.db_pool = _Pool(self.connection)

    async def asyncTearDown(self):
        pwa_api.db_pool = self.original_pool

    async def test_saves_diagnostic_and_updates_only_skill_level(self):
        result = await pwa_api.mobile_save_diagnostic_result(
            pwa_api.MobileDiagnosticResultReq(scores=[3, 3, 3, 3, 3, 3, 3]),
            tg_id=140700248,
        )

        self.assertEqual(
            result,
            {"ok": True, "pct": 100, "level_key": "В", "vakt_level": "III"},
        )
        self.assertEqual(self.connection.inserted_diag, (140700248, [3, 3, 3, 3, 3, 3, 3], "В", 100))
        self.assertEqual(self.connection.updated_participant, ("III", 77))


if __name__ == "__main__":
    unittest.main()
