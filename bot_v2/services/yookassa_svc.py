"""ЮKassa REST API — async wrapper (SDK синхронный, запускаем в executor)."""
import asyncio
import uuid
from functools import partial

from yookassa import Configuration, Payment

_configured = False

# После оплаты ЮKassa редиректит сюда
RETURN_URL = "https://t.me/iqbaraka_bot"


def setup_yookassa(shop_id: str, secret_key: str) -> None:
    global _configured
    if shop_id and secret_key:
        Configuration.configure(shop_id, secret_key)
        _configured = True


async def create_payment(
    tariff_id: str,
    price: int,           # рублей
    description: str,
    email: str | None,
    user_id: int,
) -> tuple[str, str]:
    """Создаёт платёж. Возвращает (payment_id, confirmation_url)."""
    idempotency_key = str(uuid.uuid4())

    payment_data: dict = {
        "amount": {"value": f"{price}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": RETURN_URL},
        "capture": True,
        "description": f"{description} — IQ Barakah",
        "metadata": {"tariff_id": tariff_id, "user_id": str(user_id)},
    }

    if email:
        payment_data["receipt"] = {
            "customer": {"email": email},
            "items": [{
                "description": description[:128],
                "quantity": "1.00",
                "amount": {"value": f"{price}.00", "currency": "RUB"},
                "vat_code": 1,          # 1 = без НДС (для ИП/ООО на УСН)
                "payment_mode": "full_payment",
                "payment_subject": "service",
            }],
        }

    loop = asyncio.get_event_loop()
    payment = await loop.run_in_executor(
        None,
        partial(Payment.create, payment_data, idempotency_key),
    )
    return payment.id, payment.confirmation.confirmation_url


async def get_payment_status(payment_id: str) -> str:
    """Возвращает: pending | waiting_for_capture | succeeded | canceled."""
    loop = asyncio.get_event_loop()
    payment = await loop.run_in_executor(None, partial(Payment.find_one, payment_id))
    return payment.status
