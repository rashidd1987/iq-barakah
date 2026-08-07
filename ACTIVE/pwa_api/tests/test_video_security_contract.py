import importlib.util
import time
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "video_security.py"
SPEC = importlib.util.spec_from_file_location("video_security_contract", MODULE)
video_security = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(video_security)


class VideoSecurityContractTests(unittest.TestCase):
    def test_signature_is_bound_to_video_user_and_expiry(self):
        now = int(time.time())
        expires_at = now + 600
        signature = video_security.video_signature("secret", "a-01-intro", 42, expires_at)
        self.assertTrue(video_security.verify_video_signature("secret", "a-01-intro", 42, expires_at, signature, now))
        self.assertFalse(video_security.verify_video_signature("secret", "a-01-intro", 43, expires_at, signature, now))
        self.assertFalse(video_security.verify_video_signature("secret", "a-01-intro", 42, expires_at, signature, expires_at + 1))

    def test_path_traversal_and_extensions_are_rejected(self):
        for value in ("../secret", "lesson.mp4", "/absolute", "A-uppercase", ""):
            with self.assertRaises(ValueError):
                video_security.video_file_path(Path("/data/lesson_videos"), value)

    def test_standard_open_and_suffix_ranges(self):
        self.assertEqual(video_security.parse_byte_range("bytes=10-19", 100), (10, 19))
        self.assertEqual(video_security.parse_byte_range("bytes=90-", 100), (90, 99))
        self.assertEqual(video_security.parse_byte_range("bytes=-10", 100), (90, 99))
        with self.assertRaises(ValueError):
            video_security.parse_byte_range("bytes=100-", 100)
        with self.assertRaises(ValueError):
            video_security.parse_byte_range("bytes=0-1,4-5", 100)

    def test_s3_key_does_not_accept_paths_from_content(self):
        self.assertEqual(video_security.s3_video_key('private/lessons', 'a-01-intro'), 'private/lessons/a-01-intro.mp4')
        with self.assertRaises(ValueError):
            video_security.s3_video_key('../public', 'a-01-intro')

    def test_s3_presign_uses_private_get_object_contract(self):
        class FakeClient:
            def generate_presigned_url(self, method, **kwargs):
                self.method = method
                self.kwargs = kwargs
                return 'https://storage.example/signed'

        client = FakeClient()
        url = video_security.s3_presigned_video_url(client, 'iq-videos', 'lessons', 'a-01-intro', 900)
        self.assertEqual(url, 'https://storage.example/signed')
        self.assertEqual(client.method, 'get_object')
        self.assertEqual(client.kwargs['Params']['Bucket'], 'iq-videos')
        self.assertEqual(client.kwargs['Params']['Key'], 'lessons/a-01-intro.mp4')
        self.assertEqual(client.kwargs['ExpiresIn'], 900)


if __name__ == "__main__":
    unittest.main()
