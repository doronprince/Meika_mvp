"""Live product price search via SerpApi's Google Shopping engine
(https://serpapi.com/google-shopping-api).

[[serpapi-graceful-degradation]]: with no SERPAPI_API_KEY configured, or on
any request failure, this returns None — never an empty list — so callers
can tell "live search unavailable" apart from "live search ran, found
nothing" and fall back to the seeded demo catalog. Same pattern
app/ai/copilot_service.py uses for a missing GEMINI_API_KEY.

Each live result is a single store's listing, not a same-product
comparison across multiple stores the way the seeded catalog is — SerpApi's
free tier doesn't group sellers per product. Price trend is always
INSUFFICIENT_DATA for live results: there's no observation history for a
listing fetched once, and asserting a trend without one would fabricate
the exact thing the XAI guardrail forbids.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SERPAPI_BASE_URL = "https://serpapi.com/search.json"

# SerpApi's `gl` (two-letter country) -> ISO 4217 currency. Limited to
# fx_service.SUPPORTED_CURRENCIES so every live price converts to KRW (the
# app's canonical stored unit) via a real live rate immediately on ingest.
COUNTRY_CURRENCY: dict[str, str] = {
    "us": "USD", "gb": "GBP", "de": "EUR", "fr": "EUR", "es": "EUR", "it": "EUR",
    "nl": "EUR", "ie": "EUR", "kr": "KRW", "jp": "JPY", "cn": "CNY", "in": "INR",
    "ca": "CAD", "au": "AUD", "nz": "NZD", "ch": "CHF", "se": "SEK", "no": "NOK",
    "dk": "DKK", "hk": "HKD", "sg": "SGD", "my": "MYR", "th": "THB", "ph": "PHP",
    "id": "IDR", "il": "ILS", "mx": "MXN", "br": "BRL", "za": "ZAR", "tr": "TRY",
    "pl": "PLN",
}

# Reverse lookup: a representative country for a given display currency, so
# "search live prices" has a sensible default `gl` when the caller doesn't
# specify one explicitly — derived from the signed-in user's
# preferred_currency.
_CURRENCY_COUNTRY: dict[str, str] = {currency: country for country, currency in reversed(COUNTRY_CURRENCY.items())}

DEFAULT_COUNTRY = "us"


def country_for_currency(currency: str | None) -> str:
    if not currency:
        return DEFAULT_COUNTRY
    return _CURRENCY_COUNTRY.get(currency.upper(), DEFAULT_COUNTRY)


@dataclass
class LiveProduct:
    title: str
    store_name: str
    price: Decimal
    currency: str
    rating: Decimal
    listing_url: str | None


async def search_live_products(query: str, country: str = DEFAULT_COUNTRY) -> list[LiveProduct] | None:
    if not settings.serpapi_api_key:
        return None

    country = country.lower()
    currency = COUNTRY_CURRENCY.get(country, "USD")

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                SERPAPI_BASE_URL,
                params={
                    "engine": "google_shopping",
                    "q": query,
                    "gl": country,
                    "api_key": settings.serpapi_api_key,
                },
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        logger.exception("SerpApi request failed")
        return None

    if "error" in data:
        logger.warning("SerpApi returned an error: %s", data["error"])
        return None

    products: list[LiveProduct] = []
    for item in data.get("shopping_results") or []:
        price = item.get("extracted_price")
        source = item.get("source")
        title = item.get("title")
        if price is None or not source or not title:
            continue
        rating = item.get("rating")
        products.append(
            LiveProduct(
                title=title,
                store_name=source,
                price=Decimal(str(price)),
                currency=currency,
                rating=Decimal(str(rating)) if rating is not None else Decimal("0"),
                listing_url=item.get("product_link"),
            )
        )
    return products
