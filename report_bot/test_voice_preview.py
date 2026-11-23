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

    async def test_each_voice_is_cached_separately_and_names_are_restricted(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, OPENAI_API_KEY='test'), patch('report_bot.voice_preview.synthesize_preview', new_callable=AsyncMock, side_effect=[b'onyx', b'ash']) as call:
            for _ in range(2):
                self.assertEqual(await cached_preview(folder, 'onyx'), b'onyx')
                self.assertEqual(await cached_preview(folder, 'ash'), b'ash')
            self.assertEqual(call.await_count, 2)
            for name in ['../../secret', 'unknown', '']:
                with self.assertRaises(ValueError): await cached_preview(folder, name)
            self.assertEqual(call.await_count, 2)

    async def test_energetic_voices_have_distinct_style_and_cached_output(self):
        from report_bot.voice_preview import preview_instructions
        self.assertIn('energetic', preview_instructions('echo'))
        self.assertIn('upbeat', preview_instructions('fable'))
        self.assertNotEqual(preview_instructions('echo'), preview_instructions('fable'))
        self.assertIn('calm', preview_instructions('cedar'))
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, OPENAI_API_KEY='test'), patch('report_bot.voice_preview.synthesize_preview', new_callable=AsyncMock, side_effect=[b'echo', b'fable']) as call:
            for _ in range(2):
                self.assertEqual(await cached_preview(folder, 'echo'), b'echo')
                self.assertEqual(await cached_preview(folder, 'fable'), b'fable')
            self.assertEqual(call.await_count, 2)
