"""Платежи через официальный yookassa SDK (как в старом боте).

Поток:
1. create_payment() — создаёт платёж, возвращает confirmation_url
2. Планировщик каждые 2 мин вызывает job_check_payments()
3. get_payment_status() проверяет статус в ЮKassa
4. При статусе "succeeded" — активируем участника и шлём урок
"""
import uuid
import asyncio
import logging
from functools import partial

logger = logging.getLogger(__name__)


def _create_payment_sync(shop_id: str, secret_key: str, amount: int,
                          description: str, return_url: str,
                          metadata: dict | None, customer_email: str | None) -> dict | None:
    """Синхронный вызов yookassa SDK — запускается в executor."""
    from yookassa import Configuration, Payment

    Configuration.account_id = shop_id
    Configuration.secret_key = secret_key

    idempotency_key = str(uuid.uuid4())
    payment_data = {
        "amount": {"value": f"{amount}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
    }
    if metadata:
        payment_data["metadata"] = metadata

    # Чек 54-ФЗ
    email = customer_email or "noreply@iq-barakah.ru"
    payment_data["receipt"] = {
        "customer": {"email": email},
        "items": [{
            "description": description[:128],
            "quantity": "1.00",
            "amount": {"value": f"{amount}.00", "currency": "RUB"},
            "vat_code": 1,
            "payment_mode": "full_payment",
            "payment_subject": "service",
        }],
    }

    payment = Payment.create(payment_data, idempotency_key)
    return {
        "id": payment.id,
        "confirmation_url": payment.confirmation.confirmation_url,
        "status": payment.status,
    }


def _get_payment_status_sync(shop_id: str, secret_key: str, payment_id: str) -> str | None:
    """Синхронный вызов yookassa SDK."""
    from yookassa import Configuration, Payment

    Configuration.account_id = shop_id
    Configuration.secret_key = secret_key
    payment = Payment.find_one(payment_id)
    return payment.status


async def create_payment(
    shop_id: str,
    secret_key: str,
    amount: int,
    description: str,
    return_url: str,
    metadata: dict | None = None,
    customer_email: str | None = None,
) -> dict | None:
    """Создаёт платёж через yookassa SDK асинхронно."""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(_create_payment_sync, shop_id, secret_key, amount,
                    description, return_url, metadata, customer_email)
        )
        return result
    except Exception as e:
        logger.error("YooKassa create_payment failed: %s", e)
        return None


async def get_payment_status(shop_id: str, secret_key: str, payment_id: str) -> str | None:
    """Проверяет статус платежа через yookassa SDK асинхронно."""
    try:
        loop = asyncio.get_event_loop()
        status = await loop.run_in_executor(
            None,
            partial(_get_payment_status_sync, shop_id, secret_key, payment_id)
        )
        return status
    except Exception as e:
        logger.error("YooKassa get_payment_status failed: %s", e)
        return None
