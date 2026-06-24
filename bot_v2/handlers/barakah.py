"""Реферальная система и баланс Баракатов."""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import User
from bot_v2.db.repositories import UserRepo
from bot_v2.services.barakah import (
    ensure_referral_code, get_referral_count, get_transactions,
)

logger = logging.getLogger(__name__)
router = Router(name="barakah")

KIND_LABELS = {
    "referral": "🎁 Реферал",
    "spend":    "💸 Оплата",
    "donate":   "🤲 Благотворительность",
    "expire":   "⏳ Истекло",
}


@router.message(Command("invite"))
async def cmd_invite(message: Message, session: AsyncSession):
    user = await UserRepo(session).get(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    code = await ensure_referral_code(session, user)
    bot_username = (await message.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{code}"

    name = message.from_user.first_name or user.name
    ref_count = await get_referral_count(session, user.id)

    text = (
        f"🤲 *Пригласи друга — получи Баракаты*\n\n"
        f"Твоя реферальная ссылка:\n"
        f"`{link}`\n\n"
        f"*Как это работает:*\n"
        f"• Друг переходит по твоей ссылке и оплачивает программу\n"
        f"• Ты получаешь 10% от его оплаты в Баракатах\n"
        f"• 1 Баракат = 1 ₽ — можно оплатить часть следующего тарифа\n\n"
        f"👥 Приглашено друзей: *{ref_count}*\n"
        f"💰 Баланс: *{user.barakah_balance} Б*"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Поделиться ссылкой",
            url=f"https://t.me/share/url?url={link}&text=Присоединяйся+к+IQ+Barakah+—+тайм-менеджмент+для+мусульман"
        )],
        [InlineKeyboardButton(text="💰 Мой баланс", callback_data="barakah_balance")],
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data == "barakah_balance")
@router.message(Command("balance"))
async def show_balance(event: Message | CallbackQuery, session: AsyncSession):
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
        user_id = event.from_user.id
    else:
        message = event
        user_id = event.from_user.id

    user = await UserRepo(session).get(user_id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    transactions = await get_transactions(session, user_id, limit=5)
    ref_count = await get_referral_count(session, user_id)

    history = ""
    if transactions:
        lines = []
        for tx in transactions:
            sign = "+" if tx.amount > 0 else ""
            label = KIND_LABELS.get(tx.kind, tx.kind)
            lines.append(f"{label}: {sign}{tx.amount} Б")
        history = "\n\n*Последние операции:*\n" + "\n".join(lines)

    text = (
        f"💰 *Баланс Баракатов*\n\n"
        f"*{user.barakah_balance} Б* = {user.barakah_balance} ₽\n\n"
        f"👥 Приглашено друзей: *{ref_count}*"
        f"{history}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Пригласить друга", callback_data="barakah_invite")],
        [InlineKeyboardButton(text="🤲 Задонатить", callback_data="barakah_donate")],
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data == "barakah_invite")
async def cb_barakah_invite(call: CallbackQuery, session: AsyncSession):
    await call.answer()
    # Переиспользуем логику cmd_invite
    user = await UserRepo(session).get(call.from_user.id)
    code = await ensure_referral_code(session, user)
    bot_username = (await call.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{code}"
    ref_count = await get_referral_count(session, call.from_user.id)

    text = (
        f"🤲 *Пригласи друга — получи Баракаты*\n\n"
        f"Твоя реферальная ссылка:\n"
        f"`{link}`\n\n"
        f"• Друг оплачивает → ты получаешь 10% в Баракатах\n"
        f"• 1 Баракат = 1 ₽\n\n"
        f"👥 Приглашено: *{ref_count}* · Баланс: *{user.barakah_balance} Б*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Поделиться",
            url=f"https://t.me/share/url?url={link}&text=Присоединяйся+к+IQ+Barakah"
        )],
    ])
    await call.message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data == "barakah_donate")
async def cb_barakah_donate(call: CallbackQuery, session: AsyncSession):
    await call.answer()
    user = await UserRepo(session).get(call.from_user.id)
    if not user or user.barakah_balance <= 0:
        await call.answer("У тебя нет Баракатов для доната", show_alert=True)
        return

    text = (
        f"🤲 *Задонатить Баракаты*\n\n"
        f"Твой баланс: *{user.barakah_balance} Б*\n\n"
        f"Все твои Баракаты будут переданы на благотворительность.\n"
        f"Куратор переведёт средства вручную и пришлёт подтверждение."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Задонатить всё", callback_data="barakah_donate_confirm")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="barakah_balance")],
    ])
    await call.message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data == "barakah_donate_confirm")
async def cb_barakah_donate_confirm(call: CallbackQuery, session: AsyncSession):
    from bot_v2.config import Config
    await call.answer()
    user = await UserRepo(session).get(call.from_user.id)
    if not user or user.barakah_balance <= 0:
        await call.answer("Баланс пуст", show_alert=True)
        return

    amount = user.barakah_balance
    from bot_v2.db.models import BarakahTransaction
    user.barakah_balance = 0
    session.add(BarakahTransaction(
        user_id=user.id,
        amount=-amount,
        kind="donate",
        note="Пользователь задонатил все баллы",
    ))
    await session.flush()

    await call.message.edit_text(
        f"🤲 *БаракАллах!*\n\n"
        f"{amount} Б переданы на благотворительность.\n"
        f"Куратор пришлёт подтверждение перевода.",
        parse_mode="Markdown",
    )

    # Уведомить куратора
    from bot_v2.config import Config as _Config
    config: _Config = call.bot["config"] if hasattr(call.bot, "__getitem__") else None
    if config:
        for curator_id in config.curator_ids:
            try:
                await call.bot.send_message(
                    curator_id,
                    f"🤲 *Донат Баракатами*\n\n"
                    f"👤 {user.name} (`{user.id}`)\n"
                    f"💰 {amount} Б → благотворительность\n"
                    f"Нужно перевести {amount} ₽",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
