"""Owner-only Telegram commands and authenticated outbound-worker endpoints."""

import asyncio
import hmac
import html
import logging
import os
import time

from aiohttp import web
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from report_bot.mac_queue import MacQueue

logger = logging.getLogger(__name__)
WORKER = 'owner-mac'


def worker_secret() -> str:
    return os.environ.get('MAC_WORKER_SECRET', '').strip()


def build_mac_router(config, queue: MacQueue) -> Router:
    router = Router(name='owner_mac')

    def owner_private(message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in config.owner_ids
                    and message.chat.type == 'private')

    @router.message(Command('mac'))
    async def run_on_mac(message: Message):
        if not owner_private(message):
            return
        if len(worker_secret()) < 32:
            await message.answer('Исполнитель Mac ещё не подключён.')
            return
        task = (message.text or '').split(maxsplit=1)
        if len(task) != 2:
            await message.answer('Напишите /mac и задачу. Например: /mac составь план публикаций и сохрани в outbox/plan.md\n\nМак работает с файлами своей рабочей папки. Изменения production остаются в Approval Center.')
            return
        try:
            job = queue.enqueue(message.from_user.id, f'{message.chat.id}:{message.message_id}', task[1])
        except ValueError as exc:
            await message.answer(html.escape(str(exc)))
            return
        await message.answer(f'Задача Mac <code>{job["id"]}</code>: {job["status"]}.\nРезультат придёт сюда. Если Mac спит, задача будет ждать.')

    @router.message(Command('macstatus'))
    async def mac_status(message: Message):
        if not owner_private(message):
            return
        last = queue.last_seen()
        status = 'ещё не подключался' if last is None else f'последний контакт {int(time.time() - last)} сек. назад'
        rows = queue.recent(message.from_user.id)
        text = '\n'.join(f'{row["id"]}: {row["status"]} — {row["task"][:100]}' for row in rows)
        await message.answer(html.escape(f'Mac: {status}\n\n{text or "Задач пока нет"}'))

    return router


def add_mac_routes(app: web.Application, queue: MacQueue):
    def authorize(request):
        secret = worker_secret()
        supplied = request.headers.get('Authorization', '')
        if len(secret) < 32 or not hmac.compare_digest(supplied.encode(), f'Bearer {secret}'.encode()):
            raise web.HTTPUnauthorized()

    def payload(job):
        return {key: job[key] for key in ('id', 'task', 'claim_token')}

    async def claim(request):
        authorize(request)
        job = queue.claim(WORKER)
        return web.json_response({'job': payload(job) if job else None})

    async def recover(request):
        authorize(request)
        return web.json_response({'jobs': [payload(job) for job in queue.recover(WORKER)]})

    async def finish(request):
        authorize(request)
        try:
            body = await request.json()
            if not isinstance(body, dict) or not isinstance(body.get('claim_token'), str):
                raise ValueError('invalid result')
            job = queue.finish(request.match_info['job_id'], WORKER, body['claim_token'],
                               body.get('status'), body.get('result'))
        except PermissionError:
            raise web.HTTPForbidden() from None
        except (ValueError, TypeError):
            raise web.HTTPBadRequest(text='invalid result') from None
        return web.json_response({'id': job['id'], 'status': job['status']})

    app.router.add_post('/mac-worker/claim', claim)
    app.router.add_get('/mac-worker/running', recover)
    app.router.add_post('/mac-worker/jobs/{job_id}/result', finish)


async def mac_result_notifications(bot, queue: MacQueue):
    while True:
        for job in queue.unnotified():
            try:
                # Plain text avoids malformed model-generated HTML.
                header = f'Mac · {job["id"]} · {job["status"]}\n\n'
                result = job['result']
                for start in range(0, len(result), 3000):
                    await bot.send_message(job['owner'], header + result[start:start + 3000], parse_mode=None)
                queue.mark_notified(job['id'])
            except Exception:
                logger.warning('Could not deliver Mac result %s', job['id'])
        await asyncio.sleep(10)
