from decimal import Decimal

from pydantic import BaseModel


class FxRatesResponse(BaseModel):
    base: str
    rates: dict[str, Decimal]
