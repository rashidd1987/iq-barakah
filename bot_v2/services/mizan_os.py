"""Safe outbound events from IQ Barakah Bot to Mizan OS."""
import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from urllib import error, request

logger = logging.getLogger(__name__)


def _signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def _post_payment_event_sync(url: str, secret: str, payload: dict) -> tuple[bool, str]:
    raw_body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    req = request.Request(
        url,
        data=raw_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Mizan-Signature": _signature(secret, raw_body),
        },
    )
    try:
        with request.urlopen(req, timeout=8) as response:
            body = response.read(600).decode("utf-8", errors="replace")
            return 200 <= response.status < 300, body
    except error.HTTPError as exc:
        body = exc.read(600).decode("utf-8", errors="replace")
        return False, f"{exc.code}: {body}"
    except Exception as exc:
        return False, str(exc)


async def notify_mizan_payment(
    config,
    *,
    payment_id: str,
    telegram_user_id: int,
    amount: int,
    tariff_id: str,
    product_name: str,
    customer_name: str = "",
    telegram_username: str = "",
    participant_activated: bool = True,
    paid_at: datetime | None = None,
) -> bool:
    """Send confirmed payment to Mizan OS without blocking bot activation."""
    url = getattr(config, "mizan_payment_webhook_url", "")
    secret = getattr(config, "mizan_payment_webhook_secret", "")
    if not url or not secret:
        return False
    payload = {
        "payment_id": str(payment_id),
        "telegram_user_id": str(telegram_user_id),
        "telegram_username": telegram_username or "",
        "customer_name": customer_name or f"Telegram {telegram_user_id}",
        "status": "succeeded",
        "amount": int(amount or 0),
        "tariff_id": tariff_id,
        "product_name": product_name or tariff_id,
        "paid_at": (paid_at or datetime.now(timezone.utc)).isoformat(),
        "participant_activated": bool(participant_activated),
    }
    ok, detail = await asyncio.to_thread(
        _post_payment_event_sync, url, secret, payload
    )
    if ok:
        logger.info("Mizan OS payment event sent: %s", payment_id)
    else:
        logger.warning("Mizan OS payment event failed %s: %s", payment_id, detail)
    return ok
