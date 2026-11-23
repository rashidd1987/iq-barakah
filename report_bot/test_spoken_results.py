import base64
import tempfile
import unittest
from report_bot.mac_queue import MacQueue


class SpokenResultsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.queue = MacQueue(self.folder.name)
        self.queue.enqueue(1, 'voice:1:40', 'Проверь статистику')
        self.job = self.queue.claim('owner-mac')

    def finish(self, voice):
        return self.queue.finish(self.job['id'], 'owner-mac', self.job['claim_token'], 'done', 'Результат', voice)

    def test_invalid_and_empty_audio_never_finishes_job(self):
        for value in ['broken base64!', base64.b64encode(b'OggS OpusHead').decode(), 'x' * 350001]:
            with self.assertRaises(ValueError): self.finish(value)
            self.assertEqual(len(self.queue.recover('owner-mac')), 1)

    def test_audio_survives_reopen_and_identical_retry(self):
        # Codec header envelope validation; real encoding tested on macOS separately.
        voice = base64.b64encode(b'OggS' + b'OpusHead' + b'\0' * 600).decode()
        self.finish(voice)
        queue = MacQueue(self.folder.name)
        row = queue.unnotified()[0]
        self.assertEqual(row['voice'], voice)
        self.finish(voice)
        with self.assertRaises(ValueError): self.finish(None)

    def test_only_one_acceptance_is_claimed(self):
        self.assertTrue(self.queue.claim_ack(self.job['id']))
        self.assertFalse(self.queue.claim_ack(self.job['id']))
