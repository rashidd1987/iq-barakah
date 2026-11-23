"""Owner-only Telegram commands and authenticated outbound-worker endpoints."""

import asyncio
import base64
import hmac
import html
import logging
import os
import time

import aiohttp
from aiohttp import web
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

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

    @router.message(Command('mac', 'macvoice'))
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
            source = f'{message.chat.id}:{message.message_id}'
            if message.text.split()[0].split('@')[0] == '/macvoice':
                source = 'voice:' + source
            job = queue.enqueue(message.from_user.id, source, task[1])
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

    @router.message(Command('voicetest'))
    async def voice_preview(message: Message):
        if not owner_private(message):
            return
        from report_bot.voice_preview import cached_preview
        parts = (message.text or '').split()
        voice = parts[1].casefold() if len(parts) == 2 else 'cedar'
        if len(parts) > 2 or voice not in {'cedar', 'onyx', 'ash', 'echo', 'fable'}:
            await message.answer('Для сравнения: /voicetest cedar, /voicetest onyx, /voicetest ash, /voicetest echo или /voicetest fable')
            return
        try:
            audio = await cached_preview(queue.path.parent, voice)
            await message.answer_voice(BufferedInputFile(audio, filename='preview.ogg'),
                caption=f'Образец ИИ-голоса {voice.title()}. Для ответов включён Onyx.')
        except (OSError, ValueError, RuntimeError, aiohttp.ClientError, asyncio.TimeoutError):
            await message.answer('Не удалось получить пробу голоса. Платный запрос автоматически не повторяется.')

    from report_bot.mac_voice import register_mac_voice
    register_mac_voice(router, config, queue, lambda: len(worker_secret()) >= 32)
    return router


def add_mac_routes(app: web.Application, queue: MacQueue):
    def authorize(request):
        secret = worker_secret()
        supplied = request.headers.get('Authorization', '')
        if len(secret) < 32 or not hmac.compare_digest(supplied.encode(), f'Bearer {secret}'.encode()):
            raise web.HTTPUnauthorized()

    def payload(job):
        return {**{key: job[key] for key in ('id', 'task', 'claim_token')},
                'voice_reply': job['source'].startswith('voice:'),
                'voice_engine': 'server-onyx'}

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
                               body.get('status'), body.get('result'), body.get('voice'))
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
                if job['source'].startswith('voice:'):
                    try:
                        from report_bot.onyx_voice import cached_onyx
                        audio = await cached_onyx(queue.path.parent, 'result-' + job['id'], result)
                        await bot.send_voice(job['owner'], BufferedInputFile(audio, filename='result.ogg'),
                            caption=f'Голосовой результат · Onyx (ИИ) · {job["id"]}')
                    except Exception as exc:
                        logger.warning('Could not deliver Onyx result %s (%s)', job['id'], type(exc).__name__)
                        await bot.send_message(job['owner'], 'Озвучка Onyx недоступна. Результат выше — текстом. Платная генерация автоматически не повторяется.')
                elif job.get('voice'):
                    try:
                        await bot.send_voice(job['owner'], BufferedInputFile(
                            base64.b64decode(job['voice']), filename='result.ogg'),
                            caption=f'Голосовой результат · {job["id"]}')
                    except Exception:
                        logger.warning('Could not deliver spoken result %s', job['id'])
                        await bot.send_message(job['owner'], 'Не удалось отправить голосовой ответ. Результат выше — текстом.')
                queue.mark_notified(job['id'])
            except Exception:
                logger.warning('Could not deliver Mac result %s', job['id'])
        await asyncio.sleep(10)
