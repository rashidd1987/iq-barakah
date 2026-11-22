"""Confirm a transcribed owner voice note before enqueuing it for the Mac."""

import html
import logging
from pathlib import Path

from aiogram import F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

from report_bot.mac_queue import MacQueue


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
        try:
            # Stable across duplicate callback deliveries and concurrent presses.
            job = queue.enqueue(callback.from_user.id,
                                f'voice:{message.chat.id}:{message.message_id}', task)
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
                await message.answer_voice(FSInputFile(Path(__file__).parent / 'assets' / 'mac_accepted.ogg'))
            except Exception:
                logging.getLogger(__name__).warning('Could not send spoken acceptance %s', job['id'])
