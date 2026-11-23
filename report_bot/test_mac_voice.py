import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from report_bot.mac_bridge import build_mac_router
from report_bot.mac_queue import MacQueue


class DraftState:
    def __init__(self):
        self.data = dict(voice_transcript='Создай файл outbox/voice.md с текстом Голос работает.',
                         voice_preview_id=40, voice_preview_chat=123)

    async def get_data(self):
        return self.data.copy()

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def clear(self):
        self.data.clear()


class MacVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue = MacQueue(self.temp.name)
        self.env = patch.dict(os.environ, MAC_WORKER_SECRET='test-' + 'a' * 40)
        self.env.start()
        self.speech = patch('report_bot.onyx_voice.cached_onyx', new_callable=AsyncMock, return_value=b'audio')
        self.speech.start()
        self.addCleanup(self.speech.stop)
        self.addCleanup(self.env.stop)
        router = build_mac_router(SimpleNamespace(owner_ids={123}), self.queue)
        self.prepare, self.confirm = [h.callback for h in router.callback_query.handlers]
        self.state = DraftState()

    def callback(self, action='voice:mac', owner=123, chat_type='private', message_id=40):
        return SimpleNamespace(data=action, from_user=SimpleNamespace(id=owner),
            message=SimpleNamespace(message_id=message_id,
                chat=SimpleNamespace(id=123, type=chat_type), edit_text=AsyncMock(), answer_voice=AsyncMock()),
            answer=AsyncMock())

    async def test_transcript_requires_confirmation_then_worker_returns_result(self):
        callback = self.callback()
        await self.prepare(callback, self.state)
        self.assertEqual(self.queue.recent(123), [])
        text = callback.message.edit_text.call_args.args[0]
        self.assertIn(self.state.data['voice_transcript'], text)
        callback.data = 'macvoice:run'
        await self.confirm(callback, self.state)
        jobs = self.queue.recent(123)
        self.assertEqual(len(jobs), 1)
        callback.message.answer_voice.assert_awaited_once()
        self.assertEqual(jobs[0]['task'], 'Создай файл outbox/voice.md с текстом Голос работает.')
        job = self.queue.claim('owner-mac')
        self.queue.finish(job['id'], 'owner-mac', job['claim_token'], 'done', 'Файл создан')
        self.assertEqual(self.queue.unnotified()[0]['result'], 'Файл создан')

    async def test_duplicate_confirmations_enqueue_once(self):
        callback = self.callback()
        await self.prepare(callback, self.state)
        callback.data = 'macvoice:run'
        await asyncio.gather(self.confirm(callback, self.state), self.confirm(callback, self.state))
        self.assertEqual(len(self.queue.recent(123)), 1)

    async def test_cancel_does_not_enqueue(self):
        callback = self.callback()
        await self.prepare(callback, self.state)
        callback.data = 'macvoice:cancel'
        await self.confirm(callback, self.state)
        self.assertEqual(self.queue.recent(123), [])
        self.assertEqual(self.state.data, {})

    async def test_owner_private_chat_required_at_both_steps(self):
        for owner, kind in [(456, 'private'), (123, 'group')]:
            callback = self.callback(owner=owner, chat_type=kind)
            await self.prepare(callback, self.state)
            self.assertNotIn('voice_mac_task', self.state.data)
            self.state.data.update(voice_mac_task='test task', voice_mac_message_id=40)
            callback.data = 'macvoice:run'
            await self.confirm(callback, self.state)
            self.assertEqual(self.queue.recent(123), [])
            self.state.data.pop('voice_mac_task')

    async def test_old_message_cannot_execute_new_transcript(self):
        callback = self.callback(message_id=39)
        await self.prepare(callback, self.state)
        self.assertNotIn('voice_mac_task', self.state.data)
        callback = self.callback()
        await self.prepare(callback, self.state)
        callback.data = 'macvoice:run'
        self.state.data['voice_mac_message_id'] = 41
        await self.confirm(callback, self.state)
        self.assertEqual(self.queue.recent(123), [])

    async def test_new_voice_invalidates_old_confirmation(self):
        callback = self.callback()
        await self.prepare(callback, self.state)
        await self.state.clear()
        await self.state.update_data(voice_transcript='Другая задача', voice_preview_id=42,
                                     voice_preview_chat=123)
        callback.data = 'macvoice:run'
        await self.confirm(callback, self.state)
        self.assertEqual(self.queue.recent(123), [])

    async def test_unpaired_mac_cannot_prepare_or_enqueue(self):
        callback = self.callback()
        with patch.dict(os.environ, MAC_WORKER_SECRET=''):
            await self.prepare(callback, self.state)
        self.assertNotIn('voice_mac_task', self.state.data)
        await self.prepare(callback, self.state)
        callback.data = 'macvoice:run'
        with patch.dict(os.environ, MAC_WORKER_SECRET=''):
            await self.confirm(callback, self.state)
        self.assertEqual(self.queue.recent(123), [])

    async def test_long_transcript_fits_telegram_message_limit(self):
        self.state.data['voice_transcript'] = 'a' * 4000
        callback = self.callback()
        await self.prepare(callback, self.state)
        self.assertLessEqual(len(callback.message.edit_text.call_args.args[0]), 4096)
        callback.data = 'macvoice:run'
        await self.confirm(callback, self.state)
        self.assertLessEqual(len(callback.message.edit_text.call_args.args[0]), 4096)
        self.assertEqual(len(self.queue.recent(123)), 1)

    async def test_auto_voice_owner_private_and_duplicate_delivery(self):
        from report_bot.mac_voice import auto_accept_voice
        message = SimpleNamespace(from_user=SimpleNamespace(id=123),
            chat=SimpleNamespace(id=123, type='private'), message_id=99,
            answer=AsyncMock(), answer_voice=AsyncMock())
        config = SimpleNamespace(owner_ids={123})
        with patch.dict(os.environ, MAC_VOICE_AUTO_RUN='1'):
            for _ in range(2):
                self.assertTrue(await auto_accept_voice(message, 'Проверь Gmail', config, self.queue))
            self.assertEqual(len(self.queue.recent(123)), 1)
            message.answer_voice.assert_awaited_once()
            self.assertTrue(self.queue.claim('owner-mac')['source'].startswith('voice:'))
            message.from_user.id = 456
            self.assertFalse(await auto_accept_voice(message, 'Проверь Gmail', config, self.queue))
            message.from_user.id = 123
            message.chat.type = 'group'
            self.assertFalse(await auto_accept_voice(message, 'Проверь Gmail', config, self.queue))
        with patch.dict(os.environ, MAC_VOICE_AUTO_RUN='0'):
            self.assertFalse(await auto_accept_voice(message, 'Проверь Gmail', config, self.queue))
