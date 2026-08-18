import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import ExpenseCategory, StoreType, TransitMode
from app.schemas.common import PriceTrendResult, XAIFactor


class StoreComparison(BaseModel):
    store_id: uuid.UUID
    store_name: str
    store_type: StoreType
    price_krw: Decimal
    transit_cost_krw: Decimal
    transit_mode: TransitMode
    true_economic_cost_krw: Decimal
    price_trend: PriceTrendResult
    rating: Decimal
    in_stock: bool


class PriceFinderResult(BaseModel):
    product_id: uuid.UUID
    product_name: str
    category: ExpenseCategory
    comparisons: list[StoreComparison]
    recommendation: XAIFactor
