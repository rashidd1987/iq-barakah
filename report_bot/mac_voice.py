"""Confirm a transcribed owner voice note before enqueuing it for the Mac."""

import html
import logging
import os
from pathlib import Path

from aiogram import F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile, FSInputFile

from report_bot.mac_queue import MacQueue


async def answer_acceptance(message, queue, paid):
    if paid:
        from report_bot.onyx_voice import cached_onyx, ACCEPTED
        audio = await cached_onyx(queue.path.parent, 'acceptance-v1', ACCEPTED)
        await message.answer_voice(BufferedInputFile(audio, filename='accepted.ogg'))
    else:
        await message.answer_voice(FSInputFile(Path(__file__).parent / 'assets' / 'mac_accepted.ogg'))


def register_mac_voice(router, config, queue: MacQueue, ready):
    def allowed(callback):
        return bool(callback.from_user.id in config.owner_ids and callback.message
                    and callback.message.chat.type == 'private')

    @router.callback_query(F.data == 'voice:mac')
    async def prepare(callback, state):
        if not allowed(callback):
            await callback.answer('Нет доступа', show_alert=True)
            return
        if not ready():
            await callback.answer('Исполнитель Mac ещё не подключён', show_alert=True)
            return
        data = await state.get_data()
        message = callback.message
        transcript = str(data.get('voice_transcript', '')).strip()
        if (data.get('voice_preview_id') != message.message_id
                or data.get('voice_preview_chat') != message.chat.id or not transcript):
            await callback.answer('Черновик уже истёк. Отправьте голосовое заново.', show_alert=True)
            return
        if not 3 <= len(transcript) <= 4000:
            await callback.answer('Нужна задача от 3 до 4000 символов', show_alert=True)
            return
        await state.update_data(voice_mac_task=transcript, voice_mac_message_id=message.message_id)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='✅ Запустить на Mac', callback_data='macvoice:run'),
            InlineKeyboardButton(text='❌ Отмена', callback_data='macvoice:cancel'),
        ]])
        await callback.answer()
        await message.edit_text(
            '🖥 <b>Поручение для Mac</b>\n\n' + html.escape(transcript)
            + '\n\nПроверьте текст. Рабочая папка Mac; результат придёт сюда.',
            reply_markup=keyboard,
        )

    @router.callback_query(F.data.in_({'macvoice:run', 'macvoice:cancel'}))
    async def confirm(callback, state):
        if not allowed(callback):
            await callback.answer('Нет доступа', show_alert=True)
            return
        data = await state.get_data()
        message = callback.message
        task = data.get('voice_mac_task')
        if (not task or data.get('voice_mac_message_id') != message.message_id
                or data.get('voice_preview_chat') != message.chat.id):
            await callback.answer('Черновик уже истёк. Отправьте голосовое заново.', show_alert=True)
            return
        if callback.data == 'macvoice:cancel':
            await state.clear()
            await callback.answer('Отменено')
            await message.edit_text('❌ Поручение для Mac отменено.')
            return
        if not ready():
            await callback.answer('Исполнитель Mac ещё не подключён', show_alert=True)
            return
        from report_bot.voice_mode import select_voice_task
        task, paid = select_voice_task(task)
        if not 3 <= len(task) <= 4000:
            await callback.answer('Добавьте поручение после имени голоса', show_alert=True)
            return
        try:
            # Stable across duplicate callback deliveries and concurrent presses.
            job = queue.enqueue(callback.from_user.id,
                                f'voice:{"onyx:" if paid else ""}{message.chat.id}:{message.message_id}', task)
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.clear()
        await callback.answer('Поручение принято')
        await message.edit_text(
            f'🖥 Задача Mac <code>{job["id"]}</code>: {job["status"]}.\n'
            'Результат придёт сюда. Если Mac спит, задача будет ждать.'
        )

        if queue.claim_ack(job['id']):
            try:
                await answer_acceptance(message, queue, paid)
            except Exception:
                logging.getLogger(__name__).warning('Could not send spoken acceptance %s', job['id'])


async def auto_accept_voice(message, transcript, config, queue):
    """Owner opted into immediate voice tasks; production approvals remain separate."""
    if (queue is None or os.environ.get('MAC_VOICE_AUTO_RUN', '1') != '1'
            or message.from_user is None or message.from_user.id not in config.owner_ids
            or message.chat.type != 'private'):
        return False
    from report_bot.mac_bridge import worker_secret
    if len(worker_secret()) < 32:
        return False
    if not isinstance(transcript, str) or not 3 <= len(transcript.strip()) <= 4000:
        await message.answer('Не удалось принять поручение: нужна расшифровка от 3 до 4000 символов.')
        return True
    from report_bot.voice_mode import select_voice_task
    transcript, paid = select_voice_task(transcript)
    if len(transcript) < 3:
        await message.answer('Добавьте поручение после имени голоса.')
        return True
    try:
        job = queue.enqueue(message.from_user.id,
                            f'voice:{"onyx:" if paid else ""}auto:{message.chat.id}:{message.message_id}', transcript.strip())
    except ValueError as exc:
        await message.answer(html.escape(str(exc)))
        return True
    if queue.claim_ack(job['id']):
        await message.answer('🖥 Принято на Mac: ' + html.escape(transcript.strip())
                             + f'\nЗадача <code>{job["id"]}</code>. Голос: {"Onyx (платный)" if paid else "Юрий (локально)"}. Результат придёт текстом и голосом.')
        try:
            await answer_acceptance(message, queue, paid)
        except Exception:
            logging.getLogger(__name__).warning('Could not send spoken acceptance %s', job['id'])
    return True
