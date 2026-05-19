"""Платежи — ЮKassa + Telegram Payments."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, Message, PreCheckoutQuery,
    LabeledPrice, SuccessfulPayment,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.config import Config
from bot_v2.db.repositories import PaymentRepo, ParticipantRepo, UserRepo
from bot_v2.keyboards import kb_tariffs, kb_tariff_detail, kb_curator_notify
from bot_v2.services.program import get_tariff, TARIFFS

router = Router(name="payments")


class PayStates(StatesGroup):
    await_email = State()


@router.callback_query(F.data == "show_tariffs")
async def cb_show_tariffs(call: CallbackQuery):
    await call.answer()
    text = "🎓 *Тарифы IQ Barakah*\n\nВыбери программу:"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb_tariffs())


@router.callback_query(F.data.startswith("tariff:"))
async def cb_tariff_detail(call: CallbackQuery):
    tariff_id = call.data.split(":")[1]
    t = get_tariff(tariff_id)
    if not t:
        await call.answer("Тариф не найден.")
        return
    await call.answer()
    text = f"*{t['name']}*\n_{t['desc']}_\n\n💰 {t['price']:,} ₽".replace(",", " ")
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb_tariff_detail(tariff_id))


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery, state: FSMContext, session: AsyncSession, config: Config):
    tariff_id = call.data.split(":")[1]
    t = get_tariff(tariff_id)
    if not t:
        await call.answer("Тариф не найден.")
        return

    if tariff_id in ("jamaat", "leader"):
        await call.answer()
        await call.message.answer(
            f"*{t['name']}*\n\n"
            "Для записи свяжитесь с менеджером:\n"
            "📞 *+7 989 470 80 66* (WhatsApp)\n\n"
            "Менеджер расскажет об условиях и ответит на вопросы.",
            parse_mode="Markdown"
        )
        return

    # Telegram Payments (Stars или провайдер)
    if not config.payments_provider_token:
        await call.answer("Оплата временно недоступна. Напишите куратору.", show_alert=True)
        return

    await call.answer()
    uid = str(call.from_user.id)
    repo = UserRepo(session)
    user = await repo.get(call.from_user.id)
    email = user.email if user else None

    if not email:
        await state.update_data(pending_tariff=tariff_id)
        await state.set_state(PayStates.await_email)
        await call.message.answer(
            "📧 Введи email для чека ЮKassa:\n_(нажми /skip если не нужен)_",
            parse_mode="Markdown"
        )
        return

    await _send_invoice(call.message, tariff_id, t, config, email)


@router.message(PayStates.await_email)
async def msg_pay_email(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    email = None
    if message.text and message.text.lower() != "/skip" and "@" in message.text:
        email = message.text.strip()
        repo = UserRepo(session)
        await repo.update(message.from_user.id, email=email)

    data = await state.get_data()
    tariff_id = data.get("pending_tariff", "vakt")
    t = get_tariff(tariff_id)
    await state.clear()
    await _send_invoice(message, tariff_id, t, config, email)


async def _send_invoice(message: Message, tariff_id: str, tariff: dict, config: Config, email: str | None):
    await message.answer_invoice(
        title=tariff["name"],
        description=tariff["desc"],
        payload=f"{tariff_id}:{message.from_user.id}",
        provider_token=config.payments_provider_token,
        currency="RUB",
        prices=[LabeledPrice(label=tariff["name"], amount=tariff["price"] * 100)],
        need_email=not email,
        send_email_to_provider=not email,
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, session: AsyncSession, config: Config):
    payment: SuccessfulPayment = message.successful_payment
    payload = payment.invoice_payload
    tariff_id, user_id_str = payload.split(":", 1)
    user_id = int(user_id_str)

    repo = PaymentRepo(session)
    p = await repo.create(
        user_id=user_id,
        tariff_id=tariff_id,
        amount=payment.total_amount // 100,
        tg_charge_id=payment.telegram_payment_charge_id,
    )
    await repo.mark_paid(p.id, tg_charge_id=payment.telegram_payment_charge_id)

    tariff = get_tariff(tariff_id)
    await message.answer(
        f"✅ *Оплата получена!*\n\n"
        f"*{tariff['name']}* — {payment.total_amount // 100:,} ₽\n\n"
        "Куратор активирует тебя в программе в течение 24 часов. ин ша Аллах 🌿",
        parse_mode="Markdown"
    )

    # Уведомляем кураторов
    from bot_v2.db.repositories import UserRepo
    user_repo = UserRepo(session)
    user = await user_repo.get(user_id)
    name = user.name if user else str(user_id)

    for curator_id in config.curator_ids:
        try:
            await message.bot.send_message(
                chat_id=curator_id,
                text=(
                    f"💳 *Новая оплата!*\n\n"
                    f"👤 {name} (`{user_id}`)\n"
                    f"📦 Тариф: *{tariff['name']}*\n"
                    f"💰 {payment.total_amount // 100:,} ₽"
                ),
                parse_mode="Markdown",
                reply_markup=kb_curator_notify(user_id, tariff_id),
            )
        except Exception:
            pass
