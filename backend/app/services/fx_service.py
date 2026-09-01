"""Live foreign-exchange rates, sourced from a real external API
(api.frankfurter.dev — ECB reference rates, ISO 4217, no key required).

[[fx-conversion-is-display-only]]: every amount this app stores stays in
KRW. Rates from here are used two ways — (1) converting a foreign-currency
expense to KRW once, at entry time, so the stored amount_krw never drifts as
rates move later (see the expenses.original_currency/original_amount
migration), and (2) live, on-the-fly conversion for *display* in the user's
preferred_currency. Never treat a fetched rate as authoritative for
anything beyond the moment it was fetched — it's refreshed on a short TTL,
not pinned to a point in time except where explicitly snapshotted (case 1).
"""

import time
from decimal import Decimal

import httpx

FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v1"

# ECB reference rates cover these — the same set Frankfurter serves.
SUPPORTED_CURRENCIES = {
    "AUD", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP", "HKD",
    "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN", "MYR", "NOK",
    "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD", "ZAR",
}

_CACHE_TTL_SECONDS = 3600
_cache: dict[str, tuple[float, dict[str, Decimal]]] = {}


class FxRateUnavailableError(Exception):
    pass


async def get_rates(base: str = "KRW") -> dict[str, Decimal]:
    """Live rates FROM `base` TO every other supported currency, e.g.
    {"USD": Decimal("0.00073"), "EUR": Decimal("0.00063"), ...}. Cached for
    up to an hour per base currency to avoid hammering the external API."""
    base = base.upper()
    cached = _cache.get(base)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{FRANKFURTER_BASE_URL}/latest", params={"from": base})
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        if cached:
            # Serve the last known-good rates rather than fail a request
            # over a transient network blip.
            return cached[1]
        raise FxRateUnavailableError(f"Could not fetch live FX rates for {base}") from exc

    rates = {code: Decimal(str(value)) for code, value in data["rates"].items()}
    rates[base] = Decimal("1")
    _cache[base] = (now, rates)
    return rates


async def convert(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    from_currency, to_currency = from_currency.upper(), to_currency.upper()
    if from_currency == to_currency:
        return amount

    rates = await get_rates(base=from_currency)
    rate = rates.get(to_currency)
    if rate is None:
        raise FxRateUnavailableError(f"No rate from {from_currency} to {to_currency}")
    return amount * rate
