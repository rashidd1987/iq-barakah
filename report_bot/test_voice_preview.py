import os
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
from report_bot.voice_preview import cached_preview

class VoicePreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeat_uses_cached_audio_without_second_charge(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, OPENAI_API_KEY='test'), patch('report_bot.voice_preview.synthesize_preview', new_callable=AsyncMock, return_value=b'audio') as call:
            self.assertEqual(await cached_preview(folder), b'audio')
            self.assertEqual(await cached_preview(folder), b'audio')
            call.assert_awaited_once()

    async def test_failed_or_interrupted_call_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, OPENAI_API_KEY='test'), patch('report_bot.voice_preview.synthesize_preview', new_callable=AsyncMock, side_effect=RuntimeError('offline')) as call:
            with self.assertRaises(RuntimeError): await cached_preview(folder)
            with self.assertRaises(ValueError): await cached_preview(folder)
            call.assert_awaited_once()
