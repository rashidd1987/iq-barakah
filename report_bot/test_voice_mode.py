import asyncio
import base64
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from report_bot.voice_mode import select_voice_task
from report_bot.mac_voice import auto_accept_voice
from report_bot.mac_bridge import build_mac_router, mac_result_notifications
from report_bot.mac_queue import MacQueue


class VoiceModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_explicit_leading_onyx_selects_paid_voice(self):
        for text in ['Оникс, проверь Gmail', 'ONYX проверь Gmail', 'Оникс — проверь Gmail']:
            self.assertEqual(select_voice_task(text), ('проверь Gmail', True))
        for text in ['Проверь Gmail', 'Расскажи про Onyx', 'ониксовый камень']:
            self.assertEqual(select_voice_task(text), (text, False))

    async def test_default_voice_never_calls_cloud_and_explicit_onyx_does(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', MAC_WORKER_SECRET='x'*40, MAC_VOICE_AUTO_RUN='1'), patch('report_bot.onyx_voice.cached_onyx', new_callable=AsyncMock, return_value=b'onyx') as cloud:
            queue = MacQueue(folder)
            message = SimpleNamespace(from_user=SimpleNamespace(id=123), chat=SimpleNamespace(id=123, type='private'), message_id=1, answer=AsyncMock(), answer_voice=AsyncMock())
            config = SimpleNamespace(owner_ids={123})
            await auto_accept_voice(message, 'Проверь Gmail', config, queue)
            cloud.assert_not_awaited()
            first = queue.claim('test')
            self.assertFalse(first['source'].startswith('voice:onyx:'))
            queue.finish(first['id'], 'test', first['claim_token'], 'done', 'Готово')
            message.message_id = 2
            await auto_accept_voice(message, 'Оникс, проверь Gmail', config, queue)
            cloud.assert_awaited_once()
            second = queue.claim('test')
            self.assertEqual(second['task'], 'проверь Gmail')
            self.assertTrue(second['source'].startswith('voice:onyx:'))

    async def test_onyx_text_command_and_default_macvoice_have_distinct_sources(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', MAC_WORKER_SECRET='x'*40):
            queue = MacQueue(folder)
            handler = build_mac_router(SimpleNamespace(owner_ids={123}), queue).message.handlers[0].callback
            message = SimpleNamespace(from_user=SimpleNamespace(id=123), chat=SimpleNamespace(id=123,type='private'), message_id=1,text='/macvoice Проверь Gmail',answer=AsyncMock())
            await handler(message)
            first = queue.claim('test')
            self.assertFalse(first['source'].startswith('voice:onyx:'))
            queue.finish(first['id'], 'test', first['claim_token'], 'done', 'Готово')
            message.message_id=2; message.text='/onyx Проверь Gmail'
            await handler(message)
            self.assertTrue(queue.claim('test')['source'].startswith('voice:onyx:'))

    async def test_local_result_does_not_call_paid_tts(self):
        job=dict(id='123456abcdef', owner=123, source='voice:auto:123:99',status='done',result='Готово',voice=base64.b64encode(b'local').decode())
        queue=SimpleNamespace(path=Path('/tmp/jobs.sqlite3'),unnotified=lambda:[job],mark_notified=lambda _:None)
        bot=SimpleNamespace(send_message=AsyncMock(),send_voice=AsyncMock())
        with patch('report_bot.onyx_voice.cached_onyx',new_callable=AsyncMock) as cloud, patch('report_bot.mac_bridge.asyncio.sleep',side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError): await mac_result_notifications(bot,queue)
            cloud.assert_not_awaited()
            self.assertIn('Юрий',bot.send_voice.call_args.kwargs['caption'])
