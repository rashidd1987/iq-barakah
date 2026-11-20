import concurrent.futures
import tempfile
import unittest

from report_bot.mac_queue import MacQueue


class MacQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue = MacQueue(self.temp.name)

    def job(self, source='telegram:1'):
        return self.queue.enqueue(123, source, 'Сохрани рабочий план')

    def test_duplicate_telegram_delivery_creates_one_job(self):
        first = self.job()
        self.assertEqual(first['id'], self.job()['id'])
        self.assertEqual(len(self.queue.recent(123)), 1)

    def test_two_workers_cannot_claim_same_or_parallel_jobs(self):
        self.job()
        self.job('telegram:2')
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(self.queue.claim, ['mac-a', 'mac-b']))
        self.assertEqual(sum(r is not None for r in results), 1)

    def test_restart_preserves_running_job_without_reexecution(self):
        self.job()
        claimed = self.queue.claim('owner-mac')
        restarted = MacQueue(self.temp.name)
        self.assertIsNone(restarted.claim('owner-mac'))
        self.assertEqual(restarted.recover('owner-mac')[0]['id'], claimed['id'])

    def test_wrong_claim_cannot_complete_task(self):
        self.job()
        claimed = self.queue.claim('owner-mac')
        with self.assertRaises(PermissionError):
            self.queue.finish(claimed['id'], 'owner-mac', 'wrong', 'done', 'result')
        with self.assertRaises(PermissionError):
            self.queue.finish(claimed['id'], 'another-mac', claimed['claim_token'], 'done', 'result')

    def test_finish_is_idempotent_but_conflicting_result_is_rejected(self):
        self.job()
        job = self.queue.claim('owner-mac')
        args = job['id'], 'owner-mac', job['claim_token'], 'done', 'result'
        self.queue.finish(*args)
        self.queue.finish(*args)
        self.assertEqual(len(self.queue.unnotified()), 1)
        with self.assertRaises(ValueError):
            self.queue.finish(job['id'], 'owner-mac', job['claim_token'], 'done', 'changed')
        self.queue.mark_notified(job['id'])
        self.assertFalse(self.queue.unnotified())

    def test_queue_limits_and_owner_isolation(self):
        for i in range(20):
            self.job(str(i))
        with self.assertRaises(ValueError):
            self.job('overflow')
        self.assertFalse(self.queue.recent(456))


if __name__ == '__main__':
    unittest.main()
