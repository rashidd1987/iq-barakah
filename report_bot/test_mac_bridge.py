import os
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
from types import SimpleNamespace

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from report_bot.mac_bridge import add_mac_routes, build_mac_router
from report_bot.mac_queue import MacQueue


class MacBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.secret = 'test-only-' + 'a' * 40
        self.environment = patch.dict(os.environ, MAC_WORKER_SECRET=self.secret)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.queue = MacQueue(self.temp.name)
        app = web.Application()
        add_mac_routes(app, self.queue)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
        self.headers = {'Authorization': 'Bearer ' + self.secret}

    async def test_unauthenticated_worker_cannot_read_or_claim_jobs(self):
        self.queue.enqueue(123, '1', 'private owner task')
        for method, route in [('post', '/mac-worker/claim'), ('get', '/mac-worker/running'),
                              ('post', '/mac-worker/jobs/any/result')]:
            response = await getattr(self.client, method)(route)
            self.assertEqual(response.status, 401)

    async def test_unconfigured_bridge_denies_even_empty_bearer(self):
        with patch.dict(os.environ, MAC_WORKER_SECRET=''):
            response = await self.client.post('/mac-worker/claim', headers={'Authorization': 'Bearer '})
            self.assertEqual(response.status, 401)

    async def test_claim_result_retries_and_recovery(self):
        original = self.queue.enqueue(123, '1', 'write a plan')
        response = await self.client.post('/mac-worker/claim', headers=self.headers)
        job = (await response.json())['job']
        self.assertEqual(job['id'], original['id'])
        response = await self.client.post('/mac-worker/claim', headers=self.headers)
        self.assertIsNone((await response.json())['job'])
        response = await self.client.get('/mac-worker/running', headers=self.headers)
        self.assertEqual(len((await response.json())['jobs']), 1)
        result = {'claim_token': job['claim_token'], 'status': 'done', 'result': 'Saved plan'}
        for _ in range(2):
            response = await self.client.post(f'/mac-worker/jobs/{job["id"]}/result', headers=self.headers, json=result)
            self.assertEqual(response.status, 200)
        response = await self.client.get('/mac-worker/running', headers=self.headers)
        self.assertEqual((await response.json())['jobs'], [])

    async def test_invalid_claim_and_malformed_payload(self):
        self.queue.enqueue(123, '1', 'write a plan')
        job = self.queue.claim('owner-mac')
        route = f'/mac-worker/jobs/{job["id"]}/result'
        response = await self.client.post(route, headers=self.headers, json=[])
        self.assertEqual(response.status, 400)
        response = await self.client.post(route, headers=self.headers,
            json={'claim_token': 'wrong', 'status': 'done', 'result': 'x'})
        self.assertEqual(response.status, 403)

    async def test_cloud_http_identity_isolated_from_mac_and_unknown_workers(self):
        original = self.queue.enqueue(123, 'cloud', 'Проверь Gmail')
        response = await self.client.post('/mac-worker/claim', headers=self.headers)
        self.assertIsNone((await response.json())['job'])
        cloud = {**self.headers, 'X-Mizan-Worker': 'cloud-readers'}
        response = await self.client.post('/mac-worker/claim', headers=cloud)
        job = (await response.json())['job']
        self.assertEqual(job['id'], original['id'])
        result = {'claim_token': job['claim_token'], 'status': 'done', 'result': 'API result'}
        route = f'/mac-worker/jobs/{job["id"]}/result'
        response = await self.client.post(route, headers=self.headers, json=result)
        self.assertEqual(response.status, 403)
        response = await self.client.post(route, headers=cloud, json=result)
        self.assertEqual(response.status, 200)
        response = await self.client.post('/mac-worker/claim', headers={**cloud, 'X-Mizan-Worker': 'unknown'})
        self.assertEqual(response.status, 403)

    async def test_only_owner_in_private_chat_can_enqueue(self):
        router = build_mac_router(SimpleNamespace(owner_ids={123}), self.queue)
        handler = router.message.handlers[0].callback
        for user_id, chat_type in [(456, 'private'), (123, 'group')]:
            message = SimpleNamespace(from_user=SimpleNamespace(id=user_id),
                chat=SimpleNamespace(id=123, type=chat_type), message_id=1,
                text='/mac save a plan', answer=AsyncMock())
            await handler(message)
            message.answer.assert_not_awaited()
        self.assertFalse(self.queue.recent(123))
        message = SimpleNamespace(from_user=SimpleNamespace(id=123),
            chat=SimpleNamespace(id=123, type='private'), message_id=1,
            text='/mac save a plan', answer=AsyncMock())
        await handler(message)
        self.assertEqual(len(self.queue.recent(123)), 1)
