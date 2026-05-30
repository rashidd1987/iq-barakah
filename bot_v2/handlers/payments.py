"""Платежи — ЮKassa + Telegram Payments."""
import json
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
from bot_v2.services.i18n import t
from bot_v2.services.program import get_tariff, get_tariff_view

router = Router(name="payments")


class PayStates(StatesGroup):
    await_email = State()


@router.callback_query(F.data == "show_tariffs")
async def cb_show_tariffs(call: CallbackQuery, session: AsyncSession):
    await call.answer()
    lang = await _user_lang(session, call.from_user.id)
    await call.message.edit_text(t(lang, "tariffs.title"), parse_mode="Markdown", reply_markup=kb_tariffs(lang))


@router.callback_query(F.data.startswith("tariff:"))
async def cb_tariff_detail(call: CallbackQuery, session: AsyncSession):
    lang = await _user_lang(session, call.from_user.id)
    tariff_id = call.data.split(":")[1]
    tariff = get_tariff(tariff_id)
    if not tariff:
        await call.answer(t(lang, "tariffs.not_found"))
        return
    tariff_view = get_tariff_view(tariff_id, lang) or tariff
    await call.answer()
    text = f"*{tariff_view['name']}*\n_{tariff_view['desc']}_\n\n💰 {tariff['price']:,} ₽".replace(",", " ")
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb_tariff_detail(tariff_id, lang))


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery, state: FSMContext, session: AsyncSession, config: Config):
    lang = await _user_lang(session, call.from_user.id)
    tariff_id = call.data.split(":")[1]
    tariff = get_tariff(tariff_id)
    if not tariff:
        await call.answer(t(lang, "tariffs.not_found"))
        return

    if tariff_id in ("jamaat", "leader"):
        tariff_view = get_tariff_view(tariff_id, lang) or tariff
        await call.answer()
        await call.message.answer(
            f"*{tariff_view['name']}*\n\n"
            f"{t(lang, 'payments.manager')}",
            parse_mode="Markdown"
        )
        return

    # Telegram Payments (Stars или провайдер)
    if not config.payments_provider_token:
        await call.answer(t(lang, "payments.unavailable"), show_alert=True)
        return

    await call.answer()
    repo = UserRepo(session)
    user = await repo.get(call.from_user.id)
    email = user.email if user else None

    if not email:
        await state.update_data(pending_tariff=tariff_id, lang=lang)
        await state.set_state(PayStates.await_email)
        await call.message.answer(
            t(lang, "payments.email"),
            parse_mode="Markdown"
        )
        return

    await _send_invoice(call.message, tariff_id, tariff, config, email, lang)


@router.message(PayStates.await_email)
async def msg_pay_email(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    email = None
    if message.text and message.text.lower() != "/skip" and "@" in message.text:
        email = message.text.strip()
        repo = UserRepo(session)
        await repo.update(message.from_user.id, email=email)

    data = await state.get_data()
    tariff_id = data.get("pending_tariff", "vakt")
    lang = data.get("lang") or await _user_lang(session, message.from_user.id)
    tariff = get_tariff(tariff_id)
    await state.clear()
    await _send_invoice(message, tariff_id, tariff, config, email, lang)


async def _send_invoice(
    message: Message,
    tariff_id: str,
    tariff: dict,
    config: Config,
    email: str | None,
    lang: str,
):
    tariff_view = get_tariff_view(tariff_id, lang) or tariff

    # ЮKassa LIVE требует данные чека (ФЗ-54): email и состав заказа
    provider_data = json.dumps({
        "receipt": {
            "customer": {"email": email or "noreply@iqbarakah.ru"},
            "items": [{
                "description": tariff_view["name"][:128],
                "quantity": "1.00",
                "amount": {
                    "value": f"{tariff['price']:.2f}",
                    "currency": "RUB",
                },
                "vat_code": 6,          # без НДС (УСН)
                "payment_mode": "full_prepayment",
                "payment_subject": "service",
            }],
        }
    })

    await message.answer_invoice(
        title=tariff_view["name"],
        description=tariff_view["desc"],
        payload=f"{tariff_id}:{message.from_user.id}",
        provider_token=config.payments_provider_token,
        currency="RUB",
        prices=[LabeledPrice(label=tariff_view["name"], amount=tariff["price"] * 100)],
        need_email=not email,
        send_email_to_provider=True,
        provider_data=provider_data,
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
    user_repo = UserRepo(session)
    user = await user_repo.get(user_id)
    lang = user.language_code if user else "ru"
    tariff_view = get_tariff_view(tariff_id, lang) or tariff
    await message.answer(
        t(
            lang,
            "payments.success",
            tariff=tariff_view["name"],
            amount=f"{payment.total_amount // 100:,}".replace(",", " "),
        ),
        parse_mode="Markdown"
    )

    # Уведомляем кураторов
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


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
