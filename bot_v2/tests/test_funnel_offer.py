"""Воронка Старта: цена со скидкой, карточка, пропуск вопросов с сайта."""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot_v2.handlers import korablik, payments


class _FakeSettings:
    store: dict = {}

    def __init__(self, session):
        pass

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value


@pytest.fixture(autouse=True)
def fake_settings():
    _FakeSettings.store = {}
    with patch("bot_v2.db.repositories.SettingsRepo", _FakeSettings):
        yield _FakeSettings.store


@pytest.mark.asyncio
async def test_vakt_full_price_without_offer():
    price, exp = await payments._effective_price(None, "vakt", 1)
    assert (price, exp) == (1500, None)


@pytest.mark.asyncio
async def test_vakt_discount_after_korablik(fake_settings):
    fake_settings["korablik_offer:1"] = str(int(time.time()) + 3600)
    price, exp = await payments._effective_price(None, "vakt", 1)
    assert price == 999 and exp


@pytest.mark.asyncio
async def test_vakt_discount_expired(fake_settings):
    fake_settings["korablik_offer:1"] = str(int(time.time()) - 10)
    price, _ = await payments._effective_price(None, "vakt", 1)
    assert price == 1500


def test_card_shows_discount_and_result():
    text = payments._vakt_card_text(999, int(time.time()) + 3600)
    assert "999" in text and "1 500" in text and "6 шагов" in text
    text = payments._vakt_card_text(1500, None)
    assert "разовая оплата" in text


@pytest.mark.asyncio
async def test_duplicate_paid_answers_with_message_not_second_alert():
    call = MagicMock()
    call.data = "pay:vakt"
    call.from_user.id = 1
    call.answer = AsyncMock()
    call.message.answer = AsyncMock()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=SimpleNamespace(status="paid"))
    with patch.object(payments, "_user_lang", AsyncMock(return_value="ru")):
        await payments.cb_pay(call, session, MagicMock())
    assert call.answer.await_count == 1  # только ранний answer()
    call.message.answer.assert_awaited_once()
    assert "уже есть доступ" in call.message.answer.await_args.args[0]


def test_advance_skips_site_answered_questions():
    scores = [1]  # ответили на отсек 1
    nxt = korablik._advance(scores, 1, {1: 2, 2: 0})
    assert nxt == 3 and scores == [1, 2, 0]


def test_advance_without_prefill():
    scores = [1]
    assert korablik._advance(scores, 1, {}) == 1 and scores == [1]
