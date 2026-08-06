import asyncio
import base64
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('JWT_SECRET', 'test-secret')
os.environ.setdefault('YOOKASSA_SHOP_ID', 'test-shop')
os.environ.setdefault('YOOKASSA_SECRET_KEY', 'test-key')

MODULE = Path(__file__).resolve().parents[1] / 'main.py'
SPEC = importlib.util.spec_from_file_location('pwa_api_payment_contract', MODULE)
pwa_api = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pwa_api)


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            'id': 'payment-1',
            'status': 'pending',
            'confirmation': {'confirmation_url': 'https://pay.example/1'},
        }).encode()


class _SettingsConnection:
    def __init__(self, values):
        self.values = values

    async def fetchval(self, _query, key):
        return self.values.get(key)


class PaymentContractTests(unittest.TestCase):
    def test_tariff_input_is_server_allowlisted(self):
        with self.assertRaises(Exception):
            pwa_api.MobilePaymentCreateReq(tariff_id='custom-price')

    def test_yookassa_request_uses_basic_auth_and_idempotence(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured['request'] = request
            captured['timeout'] = timeout
            return _Response()

        with patch.object(pwa_api, 'urlopen', fake_urlopen):
            result = pwa_api._yookassa_request_sync(
                'POST', '/payments', {'capture': True}, 'request-key'
            )

        request = captured['request']
        expected_auth = base64.b64encode(b'test-shop:test-key').decode()
        self.assertEqual(request.full_url, 'https://api.yookassa.ru/v3/payments')
        self.assertEqual(request.headers['Authorization'], f'Basic {expected_auth}')
        self.assertEqual(request.headers['Idempotence-key'], 'request-key')
        self.assertEqual(json.loads(request.data), {'capture': True})
        self.assertEqual(result['id'], 'payment-1')

    def test_discount_prices_match_existing_bot_rules(self):
        now = int(pwa_api.time.time())
        conn = _SettingsConnection({
            'korablik_offer:42': str(now + 60),
            's1_offer_at:42': str(now + 60),
        })
        vakt = asyncio.run(pwa_api._payment_price(conn, 42, 'vakt'))
        season = asyncio.run(pwa_api._payment_price(conn, 42, 's1_month'))
        self.assertEqual(vakt[0], 999)
        self.assertEqual(season[0], 3_500)

    def test_payment_routes_are_registered(self):
        paths = {route.path for route in pwa_api.app.routes}
        self.assertIn('/mobile/payments/catalog', paths)
        self.assertIn('/mobile/payments', paths)
        self.assertIn('/mobile/payments/{payment_id}', paths)

    def test_self_service_tariffs_have_catalog_fields(self):
        for tariff in pwa_api.PAYMENT_TARIFFS.values():
            self.assertIsInstance(tariff['name'], str)
            self.assertIsInstance(tariff['desc'], str)
            self.assertIsInstance(tariff['price'], int)


if __name__ == '__main__':
    unittest.main()
