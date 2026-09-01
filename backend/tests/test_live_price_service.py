from decimal import Decimal

import httpx
import pytest

from app.core.config import settings
from app.services import live_price_service


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Swaps in for httpx.AsyncClient so parsing logic is tested without
    spending real SerpApi quota or depending on network availability."""

    payload: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        return _FakeResponse(self.payload)


class _FailingAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        raise httpx.ConnectTimeout("simulated network failure")


def test_country_for_currency_picks_a_stable_representative():
    assert live_price_service.country_for_currency("EUR") == "de"
    assert live_price_service.country_for_currency("usd") == "us"
    assert live_price_service.country_for_currency("KRW") == "kr"
    assert live_price_service.country_for_currency(None) == live_price_service.DEFAULT_COUNTRY
    assert live_price_service.country_for_currency("XXX") == live_price_service.DEFAULT_COUNTRY


@pytest.mark.asyncio
async def test_search_live_products_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "serpapi_api_key", "")
    result = await live_price_service.search_live_products("rice")
    assert result is None


@pytest.mark.asyncio
async def test_search_live_products_parses_a_real_shaped_payload(monkeypatch):
    """Payload shape matches SerpApi's documented google_shopping response."""
    monkeypatch.setattr(settings, "serpapi_api_key", "fake-test-key")

    _FakeAsyncClient.payload = {
        "shopping_results": [
            {
                "title": "Test Rice 10kg",
                "source": "Test Store US",
                "extracted_price": 19.99,
                "rating": 4.6,
                "product_link": "https://example.com/listing/1",
            },
            {
                # No extracted_price -- must be skipped, never fabricated.
                "title": "No price listing",
                "source": "Some Store",
            },
            {
                "title": "Test Rice 5kg",
                "source": "Test Store 2",
                "extracted_price": 9.99,
                # No rating -- must default to 0, not fabricate one.
                "product_link": "https://example.com/listing/2",
            },
        ]
    }
    monkeypatch.setattr(live_price_service.httpx, "AsyncClient", _FakeAsyncClient)

    results = await live_price_service.search_live_products("rice", country="us")

    assert results is not None
    assert len(results) == 2  # the price-less listing was skipped
    assert results[0].title == "Test Rice 10kg"
    assert results[0].store_name == "Test Store US"
    assert results[0].price == Decimal("19.99")
    assert results[0].currency == "USD"
    assert results[0].rating == Decimal("4.6")
    assert results[0].listing_url == "https://example.com/listing/1"

    assert results[1].rating == Decimal("0")


@pytest.mark.asyncio
async def test_search_live_products_returns_none_on_serpapi_error_field(monkeypatch):
    monkeypatch.setattr(settings, "serpapi_api_key", "fake-test-key")
    _FakeAsyncClient.payload = {"error": "Invalid API key"}
    monkeypatch.setattr(live_price_service.httpx, "AsyncClient", _FakeAsyncClient)

    result = await live_price_service.search_live_products("rice")
    assert result is None


@pytest.mark.asyncio
async def test_search_live_products_returns_none_on_request_failure(monkeypatch):
    monkeypatch.setattr(settings, "serpapi_api_key", "fake-test-key")
    monkeypatch.setattr(live_price_service.httpx, "AsyncClient", _FailingAsyncClient)

    result = await live_price_service.search_live_products("rice")
    assert result is None
