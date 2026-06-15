import asyncio
import hmac
import json
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

from bot_v2.services import mizan_os


@dataclass
class FakeConfig:
    mizan_payment_webhook_url: str = "https://app.mizanos.ru/api/payments/yookassa"
    mizan_payment_webhook_secret: str = "secret"


class MizanOsPaymentEventTest(unittest.TestCase):
    def test_signature_matches_hmac_sha256(self):
        raw = b'{"payment_id":"pay-1"}'
        self.assertEqual(
            mizan_os._signature("secret", raw),
            hmac.new(b"secret", raw, "sha256").hexdigest(),
        )

    def test_notify_mizan_payment_builds_signed_payload(self):
        calls = []

        async def fake_to_thread(fn, url, secret, payload):
            calls.append((url, secret, payload))
            return True, "ok"

        with patch.object(mizan_os.asyncio, "to_thread", side_effect=fake_to_thread):
            ok = asyncio.run(
                mizan_os.notify_mizan_payment(
                    FakeConfig(),
                    payment_id="pay-1",
                    telegram_user_id=140700248,
                    amount=1500,
                    tariff_id="vakt",
                    product_name="IQ Barakah Старт",
                    customer_name="Rashid",
                    telegram_username="MRashidd",
                    paid_at=datetime(2026, 6, 16, 0, 0, tzinfo=timezone.utc),
                )
            )

        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)
        url, secret, payload = calls[0]
        self.assertEqual(url, FakeConfig.mizan_payment_webhook_url)
        self.assertEqual(secret, "secret")
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["amount"], 1500)
        self.assertEqual(payload["telegram_user_id"], "140700248")
        self.assertEqual(payload["product_name"], "IQ Barakah Старт")
        json.dumps(payload, ensure_ascii=False)

    def test_notify_mizan_payment_is_disabled_without_secret(self):
        ok = asyncio.run(
            mizan_os.notify_mizan_payment(
                FakeConfig(mizan_payment_webhook_secret=""),
                payment_id="pay-1",
                telegram_user_id=1,
                amount=1500,
                tariff_id="vakt",
                product_name="IQ Barakah",
            )
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
