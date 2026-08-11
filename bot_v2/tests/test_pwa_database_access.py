import unittest

from bot_v2.db.engine import _quote_identifier


class QuoteIdentifierTests(unittest.TestCase):
    def test_accepts_safe_role_names(self):
        for value in ["IqBarakah2", "pwa_api", "_service_role", "role123"]:
            with self.subTest(value=value):
                self.assertEqual(_quote_identifier(value), f'"{value}"')

    def test_rejects_unsafe_role_names(self):
        values = ["", "role-name", "role name", 'role"; DROP TABLE users; --']
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _quote_identifier(value)


if __name__ == "__main__":
    unittest.main()
