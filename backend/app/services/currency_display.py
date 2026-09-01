"""Renders a KRW amount as prose in a user's preferred display currency.

Every amount in the system is still *stored* and computed in KRW — this
only affects human-readable strings (Financial Clarity Score factors,
Price-Finder recommendations, Copilot replies). Mirrors the frontend's
core/format/currency.dart so a figure reads the same whether it came from a
JSON numeric field the client converted itself, or from prose the backend
generated directly.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.services import fx_service

_ZERO_DECIMAL_CURRENCIES = {"JPY", "KRW", "ISK"}

_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "KRW": "₩", "CNY": "¥",
    "INR": "₹", "AUD": "A$", "CAD": "C$", "NZD": "NZ$", "HKD": "HK$",
    "SGD": "S$", "CHF": "CHF ", "SEK": "kr ", "NOK": "kr ", "DKK": "kr ",
}


class DisplayCurrency:
    def __init__(self, code: str, rate_from_krw: Decimal):
        self.code = code
        self.rate_from_krw = rate_from_krw

    def format(self, amount_krw: Decimal) -> str:
        converted = amount_krw * self.rate_from_krw
        symbol = _SYMBOLS.get(self.code, f"{self.code} ")
        decimals = Decimal("1") if self.code in _ZERO_DECIMAL_CURRENCIES else Decimal("0.01")
        quantized = converted.quantize(decimals, rounding=ROUND_HALF_UP)
        sign = "-" if quantized < 0 else ""
        magnitude = abs(quantized)
        formatted = f"{magnitude:,.0f}" if self.code in _ZERO_DECIMAL_CURRENCIES else f"{magnitude:,.2f}"
        return f"{sign}{symbol}{formatted}"


_KRW_DISPLAY = DisplayCurrency("KRW", Decimal("1"))


async def resolve_display_currency(preferred_currency: str | None) -> DisplayCurrency:
    code = (preferred_currency or "KRW").upper()
    if code == "KRW":
        return _KRW_DISPLAY

    try:
        rates = await fx_service.get_rates(base="KRW")
    except fx_service.FxRateUnavailableError:
        return _KRW_DISPLAY

    rate = rates.get(code)
    if rate is None:
        return _KRW_DISPLAY
    return DisplayCurrency(code, rate)
