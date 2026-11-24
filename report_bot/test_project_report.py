import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('project_report', Path(__file__).parents[1]/'scripts/project_report.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProjectReportTests(unittest.TestCase):
    def test_recognizes_real_voice_spelling_without_routing_mail(self):
        self.assertTrue(module.wants_project_report('Зайди и проверь мой проект IQBarak, что там творится'))
        self.assertTrue(module.wants_project_report('Сделай отчёт IQ Barakah'))
        self.assertTrue(module.wants_project_report('Проверь проект IQ Барака'))
        self.assertFalse(module.wants_project_report('Проверь почту'))
        self.assertFalse(module.wants_project_report('Напиши пост для IQ Barakah'))

    def test_scanner_does_not_read_secret_data_symlink_or_vendor(self):
        reader = unittest.mock.Mock(return_value=b'x=1')
        entries = [('100644','a',10,'.env'), ('120000','b',10,'link.py'),
                   ('100644','c',10,'data/private.py'), ('100644','d',10,'node_modules/a.py'),
                   ('100644','e',10,'report_bot/main.py')]
        counts, findings, skipped = module.inspect_snapshot(entries,reader)
        reader.assert_called_once_with('e')
        self.assertEqual(counts['python_ok'],1)
        self.assertEqual(skipped,3)
        self.assertIn('env-файл',findings[0])

    def test_syntax_failure_never_returns_source_or_secret(self):
        counts, findings, _ = module.inspect_snapshot([('100644','a',20,'bad.py')],lambda _:b'SECRET = "private"\nif (')
        self.assertEqual(counts['python_ok'],0)
        self.assertIn('bad.py',findings[0])
        self.assertNotIn('private',' '.join(findings))

    def test_failed_refresh_does_not_claim_current_snapshot(self):
        with tempfile.TemporaryDirectory() as d, patch.object(module,'ROOT',Path(d)/'repo'), patch.object(module,'git',side_effect=OSError()), patch.object(module,'urlopen',side_effect=OSError()):
            result = module.report(Path(d)/'workspace')
            self.assertEqual(result['status'],'failed')
            self.assertIn('Старый снимок не выдаётся',result['result'])
            self.assertTrue(list((Path(d)/'workspace/outbox').glob('*.md')))

    def test_report_cannot_write_through_outbox_symlink(self):
        with tempfile.TemporaryDirectory() as d, patch.object(module,'ROOT',Path(d)/'repo'), patch.object(module,'git',side_effect=OSError()), patch.object(module,'urlopen',side_effect=OSError()):
            root=Path(d);work=root/'workspace';work.mkdir();outside=root/'outside';outside.mkdir()
            (work/'outbox').symlink_to(outside)
            with self.assertRaises(ValueError):module.report(work)
            self.assertEqual(list(outside.iterdir()),[])
