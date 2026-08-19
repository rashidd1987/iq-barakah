import importlib.util
import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path


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
SPEC = importlib.util.spec_from_file_location('pwa_api_migration', MODULE_PATH)
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


class Context:
    def __init__(self, value): self.value = value
    async def __aenter__(self): return self.value
    async def __aexit__(self, *_args): return False


class MigrationConn:
    def __init__(self, fail=False, columns=('target_user_id', 'consumed_at'), fk=True, index=True):
        self.fail = fail; self.columns = columns; self.values = [fk, index]; self.executed = []
    def transaction(self): return Context(self)
    async def execute(self, statement):
        self.executed.append(statement)
        if self.fail: raise RuntimeError('mandatory DDL failed')
    async def fetch(self, *_args): return [{'column_name': value} for value in self.columns]
    async def fetchval(self, *_args): return self.values.pop(0)


class Pool:
    def __init__(self, conn): self.conn = conn
    def acquire(self): return Context(self.conn)


class MigrationBehaviorTest(unittest.IsolatedAsyncioTestCase):
    async def test_mandatory_failure_propagates_and_never_prints_ok(self):
        api.db_pool = Pool(MigrationConn(fail=True))
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaisesRegex(RuntimeError, 'mandatory DDL failed'):
            await api._run_migrations()
        self.assertNotIn('Migration OK', output.getvalue())

    async def test_partial_required_schema_is_rejected(self):
        conn = MigrationConn(columns=('target_user_id',))
        with self.assertRaisesRegex(RuntimeError, 'consumed_at'):
            await api._verify_required_schema(conn)

    async def test_missing_fk_or_index_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'FK or index'):
            await api._verify_required_schema(MigrationConn(fk=False, index=True))

    async def test_complete_schema_passes_and_migration_is_idempotent_sql(self):
        conn = MigrationConn()
        api.db_pool = Pool(conn)
        await api._run_migrations()
        ddl = '\n'.join(conn.executed)
        self.assertIn('IF NOT EXISTS', ddl)
        self.assertNotIn('DROP ', ddl.upper())


if __name__ == '__main__':
    unittest.main()
