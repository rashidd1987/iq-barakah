"""Прямые платежи через ЮKassa API (без Telegram Payments).

Поток:
1. create_payment() — создаёт платёж, возвращает confirmation_url
2. Планировщик каждые 2 мин вызывает job_check_payments()
3. get_payment_status() проверяет статус в ЮKassa
4. При статусе "succeeded" — активируем участника и шлём урок
"""
import uuid
import logging
import aiohttp

logger = logging.getLogger(__name__)

YOOKASSA_API = "https://api.yookassa.ru/v3/payments"


async def create_payment(
    shop_id: str,
    secret_key: str,
    amount: int,          # в рублях
    description: str,
    return_url: str,
    metadata: dict | None = None,
) -> dict | None:
    """
    Создаёт платёж в ЮKassa и возвращает dict с полями:
      - id: str
      - confirmation_url: str  (ссылка для пользователя)
      - status: str
    Возвращает None при ошибке.
    """
    idempotency_key = str(uuid.uuid4())
    payload = {
        "amount": {
            "value": f"{amount}.00",
            "currency": "RUB",
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url,
        },
        "capture": True,
        "description": description,
    }
    if metadata:
        payload["metadata"] = metadata

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                YOOKASSA_API,
                json=payload,
                auth=aiohttp.BasicAuth(shop_id, secret_key),
                headers={"Idempotency-Key": idempotency_key},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return {
                        "id": data["id"],
                        "confirmation_url": data["confirmation"]["confirmation_url"],
                        "status": data["status"],
                    }
                else:
                    logger.error("YooKassa error %s: %s", resp.status, data)
                    # Возвращаем ошибку для отображения пользователю
                    return {"error": True, "status_code": resp.status, "detail": data}
    except Exception as e:
        logger.error("YooKassa request failed: %s", e)
        return None


async def get_payment_status(shop_id: str, secret_key: str, payment_id: str) -> str | None:
    """Возвращает статус платежа: pending / waiting_for_capture / succeeded / canceled / None при ошибке."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{YOOKASSA_API}/{payment_id}",
                auth=aiohttp.BasicAuth(shop_id, secret_key),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("status")
                else:
                    logger.error("YooKassa get_payment error %s for %s", resp.status, payment_id)
                    return None
    except Exception as e:
        logger.error("YooKassa get_payment failed: %s", e)
        return None
