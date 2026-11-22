import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.mac_worker import process, validate_config


class MacWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {'workspace': str(self.root), 'reports_url': 'https://reports.example', 'secret': 'x' * 40}
        self.job = {'id': 'abcdef123456', 'task': 'write a plan', 'claim_token': 'test-claim'}

    def test_report_retry_does_not_execute_model_again(self):
        def execute(args, **kwargs):
            Path(args[-1]).write_text(json.dumps({'status': 'done', 'result': 'saved'}))
        with patch('scripts.mac_worker.subprocess.run', side_effect=execute) as run:
            with patch('scripts.mac_worker.api', side_effect=OSError('offline')):
                with self.assertRaises(OSError):
                    process(self.config, self.job, self.root)
            with patch('scripts.mac_worker.api'):
                process(self.config, self.job, self.root)
            self.assertEqual(run.call_count, 1)

    def test_crash_is_reported_as_unknown_without_reexecution(self):
        folder = self.root / self.job['id']
        folder.mkdir()
        (folder / 'started').touch()
        with patch('scripts.mac_worker.subprocess.run') as run, patch('scripts.mac_worker.api') as api:
            process(self.config, self.job, self.root)
            run.assert_not_called()
            self.assertEqual(api.call_args.args[2]['status'], 'unknown')

    def test_untrusted_job_id_cannot_escape_state_folder(self):
        self.job['id'] = '../../other'
        with self.assertRaises(ValueError):
            process(self.config, self.job, self.root)

    def test_corrupt_result_is_reported_without_reexecution(self):
        folder = self.root / self.job['id']
        folder.mkdir()
        (folder / 'result.json').write_text('{broken')
        with patch('scripts.mac_worker.subprocess.run') as run, patch('scripts.mac_worker.api') as api:
            process(self.config, self.job, self.root)
            run.assert_not_called()
            self.assertEqual(api.call_args.args[2]['status'], 'unknown')

    def test_reject_insecure_or_credential_bearing_origin(self):
        for url in ['http://reports.example', 'https://secret@reports.example', 'https://reports.example/?token=x']:
            with self.assertRaises(ValueError):
                validate_config({**self.config, 'reports_url': url})

    def test_https_uses_private_stdin_and_keeps_tls_and_redirect_protection(self):
        from scripts.mac_worker import api
        from types import SimpleNamespace
        with patch('scripts.mac_worker.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='{"job":null}')) as run:
            self.assertEqual(api(self.config,'/mac-worker/claim',{}), {'job':None})
        args=run.call_args.args[0];settings=run.call_args.kwargs['input']
        self.assertNotIn(self.config['secret'],' '.join(args))
        self.assertIn(self.config['secret'],settings)
        self.assertNotIn('--insecure',args)
        self.assertNotIn('--location',args)
        self.assertIn('=https',args)
        self.assertEqual(args[1],'--disable')

    def test_https_transport_failure_does_not_leak_stderr(self):
        from scripts.mac_worker import api
        from types import SimpleNamespace
        with patch('scripts.mac_worker.subprocess.run', return_value=SimpleNamespace(returncode=35, stderr=self.config['secret'])):
            with self.assertRaises(OSError) as caught:api(self.config,'/mac-worker/running')
        self.assertNotIn(self.config['secret'],str(caught.exception))
