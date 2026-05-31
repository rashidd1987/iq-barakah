"""Платежи — прямая оплата через ЮKassa API."""
import logging

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.config import Config
from bot_v2.db.repositories import PaymentRepo, ParticipantRepo, UserRepo
from bot_v2.keyboards import kb_tariffs, kb_tariff_detail, kb_curator_notify
from bot_v2.services.i18n import t
from bot_v2.services.program import get_tariff, get_tariff_view
from bot_v2.services.yookassa_svc import create_payment

logger = logging.getLogger(__name__)

# Какой уровень программы активируется при покупке тарифа
TARIFF_LEVEL_MAP = {
    "vakt":    "А",   # ВАКТ · 6 недель
    "s1_full": "Б",   # Сезон 1 · 8 недель
    "s3_full": "Б",   # 3 сезона · начинаем с Сезона 1
}

router = Router(name="payments")


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


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery, session: AsyncSession, config: Config):
    await call.answer()
    lang = await _user_lang(session, call.from_user.id)
    tariff_id = call.data.split(":")[1]
    tariff = get_tariff(tariff_id)
    if not tariff:
        await call.message.answer(t(lang, "tariffs.not_found"))
        return

    # Джамаат и Лидер — через менеджера
    if tariff_id in ("jamaat", "leader"):
        tariff_view = get_tariff_view(tariff_id, lang) or tariff
        await call.message.answer(
            f"*{tariff_view['name']}*\n\n{t(lang, 'payments.manager')}",
            parse_mode="Markdown",
        )
        return

    # Проверяем наличие ЮKassa credentials
    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        await call.message.answer(
            "⚠️ Оплата временно недоступна. Напишите куратору: @iqbarakah"
        )
        return

    user_id = call.from_user.id
    user = await UserRepo(session).get(user_id)
    tariff_view = get_tariff_view(tariff_id, lang) or tariff

    # Создаём платёж в ЮKassa
    payment = await create_payment(
        shop_id=config.yookassa_shop_id,
        secret_key=config.yookassa_secret_key,
        amount=tariff["price"],
        description=f"{tariff_view['name']} — IQ Barakah",
        return_url="https://t.me/iqbaraka_bot",
        metadata={"tariff_id": tariff_id, "user_id": str(user_id)},
    )

    if not payment:
        await call.message.answer(
            "⚠️ Не удалось создать платёж. Попробуйте позже или напишите куратору: @iqbarakah"
        )
        return

    # Записываем pending-платёж в БД
    pay_repo = PaymentRepo(session)
    db_payment = await pay_repo.create(
        user_id=user_id,
        tariff_id=tariff_id,
        amount=tariff["price"],
        tg_charge_id=payment["id"],  # yookassa payment id
    )

    name = user.name if user else "участник"
    text = (
        f"💳 *{tariff_view['name']}*\n"
        f"_{tariff_view['desc']}_\n\n"
        f"💰 Сумма: *{tariff['price']:,} ₽*\n\n"
        f"Нажми кнопку ниже для оплаты. После оплаты вернись в бот — урок придёт автоматически."
    ).replace(",", " ")

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="💳 Перейти к оплате",
            url=payment["confirmation_url"],
        )
    ]])

    await call.message.answer(text, parse_mode="Markdown", reply_markup=kb)

    # Уведомляем кураторов о новом заказе
    for curator_id in config.curator_ids:
        try:
            await call.bot.send_message(
                chat_id=curator_id,
                text=(
                    f"🔔 *Новый заказ (ожидает оплаты)*\n\n"
                    f"👤 {name} (`{user_id}`)\n"
                    f"📦 Тариф: *{tariff['name']}*\n"
                    f"💰 {tariff['price']:,} ₽\n"
                    f"🆔 ЮKassa: `{payment['id']}`"
                ).replace(",", " "),
                parse_mode="Markdown",
                reply_markup=kb_curator_notify(user_id, tariff_id),
            )
        except Exception:
            pass


async def _activate_after_payment(bot, user_id: int, tariff_id: str, session: AsyncSession, config: Config):
    """Активировать участника и отправить первый урок после подтверждения оплаты."""
    from bot_v2.handlers.program import send_weekly_lesson

    level = TARIFF_LEVEL_MAP.get(tariff_id)
    if not level:
        return

    p_repo = ParticipantRepo(session)
    participant = await p_repo.activate(user_id, level=level, week=1)
    await session.flush()

    try:
        await send_weekly_lesson(bot, user_id, participant, session, config)
    except Exception as e:
        logger.warning("send_weekly_lesson after payment failed for %s: %s", user_id, e)


async def _user_lang(session: AsyncSession, user_id: int) -> str:
    user = await UserRepo(session).get(user_id)
    return user.language_code if user else "ru"
