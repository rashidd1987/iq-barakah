import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


os.environ.setdefault('JWT_SECRET', 'video-test-jwt-secret')
MODULE = Path(__file__).resolve().parents[1] / 'main.py'
SPEC = importlib.util.spec_from_file_location('pwa_api_video_stream_contract', MODULE)
pwa_api = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pwa_api)


class VideoStreamContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / 'a-01-intro.mp4').write_bytes(b'0123456789')
        self.client = TestClient(pwa_api.app)
        self.patches = [
            patch.object(pwa_api, 'VIDEO_STORAGE_DIR', self.root),
            patch.object(pwa_api, 'VIDEO_SIGNING_SECRET', 'video-test-secret'),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp_dir.cleanup()

    def _url(self, user_id=42, expires_at=None):
        expires_at = expires_at or int(time.time()) + 600
        signature = pwa_api.video_signature('video-test-secret', 'a-01-intro', user_id, expires_at)
        return f'/mobile/videos/a-01-intro?uid={user_id}&exp={expires_at}&sig={signature}'

    def test_range_stream_and_security_headers(self):
        response = self.client.get(self._url(), headers={'Range': 'bytes=2-5'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b'2345')
        self.assertEqual(response.headers['content-range'], 'bytes 2-5/10')
        self.assertEqual(response.headers['cache-control'], 'private, no-store, max-age=0')
        self.assertEqual(response.headers['content-disposition'], 'inline')

        head = self.client.head(self._url())
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.headers['content-length'], '10')
        self.assertEqual(head.content, b'')

        invalid_range = self.client.get(self._url(), headers={'Range': 'bytes=10-'})
        self.assertEqual(invalid_range.status_code, 416)
        self.assertEqual(invalid_range.headers['content-range'], 'bytes */10')

    def test_expired_or_tampered_link_is_rejected(self):
        expired = int(time.time()) - 1
        response = self.client.get(self._url(expires_at=expired))
        self.assertEqual(response.status_code, 403)

        valid_url = self._url(user_id=42).replace('uid=42', 'uid=43')
        response = self.client.get(valid_url)
        self.assertEqual(response.status_code, 403)

    def test_content_never_returns_a_legacy_public_url(self):
        token = pwa_api.make_mobile_token(42)
        headers = {'Authorization': f'Bearer {token}'}
        with patch.object(pwa_api, '_load_lesson_content', return_value={
            'title': 'Урок', 'video': {'url': 'https://public.example/video.mp4'}
        }):
            response = self.client.get('/mobile/content/%D0%90/1', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('video', response.json())

    def test_content_exchanges_private_id_for_a_signed_url(self):
        token = pwa_api.make_mobile_token(42)
        headers = {'Authorization': f'Bearer {token}'}
        with patch.object(pwa_api, '_load_lesson_content', return_value={
            'title': 'Урок', 'video': {'id': 'a-01-intro', 'title': 'Введение'}
        }):
            response = self.client.get('/mobile/content/%D0%90/1', headers=headers)
        self.assertEqual(response.status_code, 200)
        video = response.json()['video']
        self.assertEqual(video['title'], 'Введение')
        self.assertIn('/mobile/videos/a-01-intro?', video['url'])
        self.assertNotIn('video-test-secret', video['url'])


if __name__ == '__main__':
    unittest.main()
