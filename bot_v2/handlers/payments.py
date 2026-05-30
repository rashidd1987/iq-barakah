"""Платежи — ЮKassa REST API (не Telegram Payments)."""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.config import Config
from bot_v2.db.repositories import PaymentRepo, ParticipantRepo, UserRepo
from bot_v2.keyboards import kb_tariffs, kb_tariff_detail
from bot_v2.services.i18n import t
from bot_v2.services.program import get_tariff, get_tariff_view
from bot_v2.services import yookassa_svc

logger = logging.getLogger(__name__)

router = Router(name="payments")

# Тариф → уровень программы (как в старом боте)
TARIFF_TO_LEVEL = {
    "vakt":    "А",
    "s1_full": "Б",
    "s3_full": "Б",
    "jamaat":  "Б",
    "leader":  "Г",
}


class PayStates(StatesGroup):
    await_email = State()


# ─── Тарифы ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "show_tariffs")
async def cb_show_tariffs(call: CallbackQuery, session: AsyncSession):
    await call.answer()
    lang = await _user_lang(session, call.from_user.id)
    await call.message.edit_text(
        t(lang, "tariffs.title"), parse_mode="Markdown", reply_markup=kb_tariffs(lang)
    )


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


# ─── Инициирование оплаты ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery, state: FSMContext, session: AsyncSession, config: Config):
    lang = await _user_lang(session, call.from_user.id)
    tariff_id = call.data.split(":")[1]
    tariff = get_tariff(tariff_id)
    if not tariff:
        await call.answer(t(lang, "tariffs.not_found"))
        return

    # Джамаат и Лидер Уммы — только через куратора
    if tariff_id in ("jamaat", "leader"):
        tariff_view = get_tariff_view(tariff_id, lang) or tariff
        await call.answer()
        await call.message.answer(
            f"*{tariff_view['name']}*\n\n{t(lang, 'payments.manager')}",
            parse_mode="Markdown",
        )
        return

    await call.answer()
    user = await UserRepo(session).get(call.from_user.id)
    email = user.email if user else None

    if not email:
        await state.update_data(pending_tariff=tariff_id, lang=lang)
        await state.set_state(PayStates.await_email)
        await call.message.answer(t(lang, "payments.email"), parse_mode="Markdown")
        return

    await _send_yookassa_payment(
        call.message, tariff_id, tariff, email, call.from_user.id, lang, session, config
    )


@router.message(PayStates.await_email)
async def msg_pay_email(message: Message, state: FSMContext, session: AsyncSession, config: Config):
    email = None
    if message.text and message.text.lower() != "/skip" and "@" in message.text:
        email = message.text.strip()
        await UserRepo(session).update(message.from_user.id, email=email)

    data = await state.get_data()
    tariff_id = data.get("pending_tariff", "vakt")
    lang = data.get("lang") or await _user_lang(session, message.from_user.id)
    tariff = get_tariff(tariff_id)
    await state.clear()
    await _send_yookassa_payment(
        message, tariff_id, tariff, email, message.from_user.id, lang, session, config
    )


# ─── Создание платежа через ЮKassa REST ───────────────────────────────────────

async def _send_yookassa_payment(
    message: Message,
    tariff_id: str,
    tariff: dict,
    email: str | None,
    user_id: int,
    lang: str,
    session: AsyncSession,
    config: Config,
):
    tariff_view = get_tariff_view(tariff_id, lang) or tariff

    try:
        payment_id, confirmation_url = await yookassa_svc.create_payment(
            tariff_id=tariff_id,
            price=tariff["price"],
            description=tariff_view["name"],
            email=email,
            user_id=user_id,
        )
    except Exception as e:
        logger.error("YooKassa create_payment error: %s", e)
        await message.answer(
            "⚠️ Ошибка создания платежа. Свяжитесь с куратором — мы поможем завершить оплату.",
            reply_markup=_kb_curator(),
        )
        return

    # Сохраняем платёж в БД со статусом pending
    await PaymentRepo(session).create(
        user_id=user_id,
        tariff_id=tariff_id,
        amount=tariff["price"],
        yoo_payment_id=payment_id,
        email=email,
    )

    price_fmt = f"{tariff['price']:,}".replace(",", " ")
    b = InlineKeyboardBuilder()
    b.button(text="💳 Перейти к оплате", url=confirmation_url)
    b.button(text="✅ Я оплатил", callback_data=f"check_pay:{tariff_id}")
    b.button(text="◀️ Все тарифы", callback_data="show_tariffs")
    b.adjust(1)

    await message.answer(
        f"*{tariff_view['name']}*\n\n"
        f"💰 Сумма: *{price_fmt} ₽*\n\n"
        f"Нажми «💳 Перейти к оплате» — откроется страница ЮKassa.\n"
        f"После оплаты вернись сюда и нажми «✅ Я оплатил».\n\n"
        f"_Оплачивая, ты принимаешь условия "
        f"[публичной оферты](https://iq-barakah.ru/oferta.html)._",
        parse_mode="Markdown",
        reply_markup=b.as_markup(),
    )


# ─── Проверка статуса платежа ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("check_pay:"))
async def cb_check_payment(call: CallbackQuery, session: AsyncSession, config: Config):
    await call.answer("Проверяю платёж... 🔄")
    lang = await _user_lang(session, call.from_user.id)
    tariff_id = call.data.split(":")[1]

    pay_repo = PaymentRepo(session)
    payment = await pay_repo.get_pending(call.from_user.id)

    if not payment or payment.tariff_id != tariff_id:
        await call.message.answer(
            "❌ Платёж не найден. Попробуй создать счёт заново.",
            reply_markup=_kb_curator(),
        )
        return

    try:
        status = await yookassa_svc.get_payment_status(payment.yoo_payment_id)
    except Exception as e:
        logger.error("YooKassa status check error: %s", e)
        await call.message.answer(
            "⚠️ Не удалось проверить статус. Напиши куратору.",
            reply_markup=_kb_curator(),
        )
        return

    if status == "succeeded":
        await pay_repo.mark_paid(payment.id)

        # Активируем участника
        level = TARIFF_TO_LEVEL.get(tariff_id, "А")
        await ParticipantRepo(session).activate(call.from_user.id, level=level)

        tariff = get_tariff(tariff_id)
        tariff_view = get_tariff_view(tariff_id, lang) or tariff
        price_fmt = f"{payment.amount:,}".replace(",", " ")

        await call.message.answer(
            t(lang, "payments.success",
              tariff=tariff_view["name"],
              amount=price_fmt),
            parse_mode="Markdown",
        )

        # Уведомляем кураторов
        user = await UserRepo(session).get(call.from_user.id)
        name = user.name if user else str(call.from_user.id)
        for curator_id in config.curator_ids:
            try:
                await call.bot.send_message(
                    chat_id=curator_id,
                    text=(
                        f"💳 *Новая оплата!*\n\n"
                        f"👤 {name} (`{call.from_user.id}`)\n"
                        f"📦 Тариф: *{tariff['name']}*\n"
                        f"💰 {price_fmt} ₽\n"
                        f"✅ ЮKassa: `{payment.yoo_payment_id}`"
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    elif status == "canceled":
        await pay_repo.mark_failed(payment.id)
        await call.message.answer(
            "❌ Платёж отменён. Создай новый счёт или напиши куратору.",
            reply_markup=_kb_curator(),
        )
    else:
        # pending / waiting_for_capture
        await call.message.answer(
            "⏳ Платёж ещё не подтверждён ЮKassa.\n"
            "Оплати по ссылке выше и снова нажми «✅ Я оплатил»."
        )


# ─── Вспомогательные ─────────────────────────────────────────────────────────

def _kb_curator() -> "InlineKeyboardMarkup":
    b = InlineKeyboardBuilder()
    b.button(text="💬 Написать куратору", callback_data="contact_curator")
    b.button(text="📋 Все тарифы", callback_data="show_tariffs")
    b.adjust(1)
    return b.as_markup()


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
