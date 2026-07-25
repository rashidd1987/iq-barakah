import os
import unittest
from unittest.mock import patch

from report_bot.config import load_config
from report_bot.status import format_datetime, run_icon


class ConfigTests(unittest.TestCase):
    def test_requires_bot_token(self) -> None:
        with patch.dict(
            os.environ,
            {"OWNER_TELEGRAM_IDS": "140700248"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "TELEGRAM_BOT_TOKEN"):
                load_config()

    def test_requires_numeric_owner_ids(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "not-a-number",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "numeric"):
                load_config()

    def test_loads_multiple_owner_ids(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "test-token",
                "OWNER_TELEGRAM_IDS": "140700248, 42",
            },
            clear=True,
        ):
            config = load_config()
        self.assertEqual(config.owner_ids, frozenset({140700248, 42}))


class FormattingTests(unittest.TestCase):
    def test_run_icons(self) -> None:
        self.assertEqual(run_icon("success", "completed"), "✅")
        self.assertEqual(run_icon("failure", "completed"), "❌")
        self.assertEqual(run_icon(None, "in_progress"), "⏳")

    def test_invalid_datetime_is_safe(self) -> None:
        self.assertEqual(format_datetime("invalid"), "нет данных")


if __name__ == "__main__":
    unittest.main()
