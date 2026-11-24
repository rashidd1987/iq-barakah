import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from report_bot.mac_queue import MacQueue
from report_bot.task_routing import task_target


class CloudRoutingTests(unittest.TestCase):
    def test_server_speech_bounds_memory_without_losing_words(self):
        from scripts.cloud_spoken_result import speech_chunks
        text = ' '.join(['Проверка длинного русского отчёта.'] * 30)
        chunks = speech_chunks(text)
        self.assertTrue(all(len(chunk) <= 75 for chunk in chunks))
        self.assertEqual(' '.join(chunks), text)
        self.assertTrue(all(len(chunk) <= 75 for chunk in speech_chunks('x' * 450)))

    def test_account_reads_and_blocked_writes_go_to_narrow_server(self):
        for text in ('Проверь Gmail', 'Посмотри статистику Instagram', 'Удали письма Gmail', 'Проверь проект IQ Barakah'):
            self.assertEqual(task_target(text), 'cloud')
        for text in ('Сохрани план в outbox', 'Напиши черновик поста Instagram'):
            self.assertEqual(task_target(text), 'mac')
        with patch.dict(os.environ, CLOUD_READERS_ENABLED='0'):
            self.assertEqual(task_target('Проверь Gmail'), 'mac')

    def test_sleeping_mac_cannot_block_cloud_or_claim_its_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            queue = MacQueue(folder)
            local = queue.enqueue(123, '1', 'Сохрани план')
            cloud = queue.enqueue(123, '2', 'Проверь Gmail')
            self.assertEqual(queue.claim('owner-mac', 'mac')['id'], local['id'])
            remote = queue.claim('cloud-readers', 'cloud')
            self.assertEqual(remote['id'], cloud['id'])
            self.assertIsNone(queue.claim('cloud-readers', 'cloud'))
            with self.assertRaises(PermissionError):
                queue.finish(remote['id'], 'owner-mac', remote['claim_token'], 'done', 'test')
            queue.finish(remote['id'], 'cloud-readers', remote['claim_token'], 'done', 'test')
            queue.enqueue(123, '3', 'Проверь Instagram')
            self.assertIsNotNone(queue.claim('cloud-readers', 'cloud'))

    def test_restart_keeps_cloud_claim_and_completed_result(self):
        with tempfile.TemporaryDirectory() as folder:
            queue = MacQueue(folder)
            queue.enqueue(123, '1', 'Проверь Gmail')
            job = queue.claim('cloud-readers', 'cloud')
            restarted = MacQueue(folder)
            self.assertEqual(restarted.recover('cloud-readers')[0]['id'], job['id'])
            self.assertFalse(restarted.recover('owner-mac'))
            self.assertIsNone(restarted.claim('cloud-readers', 'cloud'))
            restarted.finish(job['id'], 'cloud-readers', job['claim_token'], 'done', 'API result')
            restarted.finish(job['id'], 'cloud-readers', job['claim_token'], 'done', 'API result')
            self.assertEqual(len(restarted.unnotified()), 1)

    def test_old_database_migration_keeps_running_mac_job(self):
        with tempfile.TemporaryDirectory() as folder:
            queue = MacQueue(folder)
            job = queue.enqueue(123, '1', 'Сохрани план')
            queue.claim('owner-mac', 'mac')
            with sqlite3.connect(queue.path) as db:
                db.execute('ALTER TABLE jobs DROP COLUMN target')
            restarted = MacQueue(folder)
            saved = restarted.recover('owner-mac')[0]
            self.assertEqual((saved['id'], saved['target'], saved['status']), (job['id'], 'mac', 'running'))

    def test_cloud_process_never_imports_local_model(self):
        import sys
        scripts = str(Path(__file__).parents[1] / 'scripts')
        with patch.object(sys, 'path', [scripts] + sys.path):
            spec = importlib.util.spec_from_file_location('cloud_assistant_test', Path(scripts) / 'cloud_assistant.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with patch.object(module, 'account_report', return_value={'status': 'done', 'result': 'API response'}):
                self.assertIn('Mac не использовался', module.execute('Проверь Gmail')['result'])
            with patch.object(module, 'account_report', return_value=None):
                self.assertEqual(module.execute('Запусти приложение')['status'], 'failed')
