import importlib.util
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / "scripts" / "import_yandex_disk_video.py"
SPEC = importlib.util.spec_from_file_location("yandex_video_import_contract", MODULE)
video_import = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(video_import)


class FakeS3Client:
    def upload_file(self, filename, bucket, key, ExtraArgs, Config):
        self.filename = filename
        self.bucket = bucket
        self.key = key
        self.extra_args = ExtraArgs

    def head_object(self, Bucket, Key):
        return {"ContentLength": Path(self.filename).stat().st_size}


class YandexVideoImportContractTests(unittest.TestCase):
    def test_upload_is_private_mp4_without_public_acl(self):
        client = FakeS3Client()
        fake_transfer = types.SimpleNamespace(TransferConfig=lambda **kwargs: kwargs)
        with patch.dict("sys.modules", {"boto3.s3.transfer": fake_transfer}):
            with tempfile.TemporaryDirectory() as directory:
                video = Path(directory) / "lesson.mp4"
                video.write_bytes(b"video")
                video_import.upload_private(client, video, "private-bucket", "lesson-videos/a-01-intro.mp4")
        self.assertEqual(client.bucket, "private-bucket")
        self.assertEqual(client.key, "lesson-videos/a-01-intro.mp4")
        self.assertEqual(client.extra_args["ContentType"], "video/mp4")
        self.assertNotIn("ACL", client.extra_args)

    def test_missing_credentials_are_reported_without_values(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "VIDEO_S3_ENDPOINT_URL"):
                video_import.private_s3_client()


if __name__ == "__main__":
    unittest.main()
