import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

from report_bot.onyx_voice import cached_onyx, spoken_summary


class OnyxVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeat_uses_cache_and_never_charges_again(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, OPENAI_API_KEY='test'), patch('report_bot.onyx_voice.synthesize_text', new_callable=AsyncMock, return_value=b'onyx') as call:
            for _ in range(2):
                self.assertEqual(await cached_onyx(folder, 'result-123456abcdef', 'Проверено'), b'onyx')
            call.assert_awaited_once_with('test', 'onyx', 'Проверено')

    async def test_timeout_never_retries_paid_synthesis(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, OPENAI_API_KEY='test'), patch('report_bot.onyx_voice.synthesize_text', new_callable=AsyncMock, side_effect=TimeoutError) as call:
            with self.assertRaises(TimeoutError): await cached_onyx(folder, 'acceptance-v1', 'Принято')
            with self.assertRaises(ValueError): await cached_onyx(folder, 'acceptance-v1', 'Принято')
            call.assert_awaited_once()

    async def test_gmail_summary_omits_addresses_and_groups_security_notices(self):
        text = 'Gmail: непрочитанные\n- [Уведомление безопасности — содержание скрыто] | secret@example.com\n- План встречи | colleague@example.com\nПисьма не изменялись.'
        summary = spoken_summary(text)
        self.assertIn('2 непрочитанных', summary)
        self.assertIn('уведомлений безопасности: 1', summary)
        self.assertIn('План встречи', summary)
        self.assertNotIn('@', summary)
        self.assertNotIn('secret', summary)

    async def test_notification_sends_text_and_onyx_even_if_legacy_audio_exists(self):
        from report_bot.mac_bridge import mac_result_notifications
        from types import SimpleNamespace
        from pathlib import Path
        job = dict(id='123456abcdef', owner=123, source='voice:auto:123:99', status='done', result='Почта проверена', voice='invalid legacy audio')
        queue = SimpleNamespace(path=Path('/tmp/jobs.sqlite3'), unnotified=lambda: [job], mark_notified=lambda _: None)
        bot = SimpleNamespace(send_message=AsyncMock(), send_voice=AsyncMock())
        with patch('report_bot.onyx_voice.cached_onyx', new_callable=AsyncMock, return_value=b'onyx') as call, patch('report_bot.mac_bridge.asyncio.sleep', side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError): await mac_result_notifications(bot, queue)
            call.assert_awaited_once_with(Path('/tmp'), 'result-123456abcdef', 'Почта проверена')
            bot.send_message.assert_awaited_once()
            bot.send_voice.assert_awaited_once()
            self.assertIn('Onyx', bot.send_voice.call_args.kwargs['caption'])
