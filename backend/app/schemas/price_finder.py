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
    # Set only for live search results (SerpApi) — a real link to the
    # actual listing. Always null for the seeded demo catalog.
    listing_url: str | None = None


class PriceFinderResult(BaseModel):
    product_id: uuid.UUID
    product_name: str
    category: ExpenseCategory
    comparisons: list[StoreComparison]
    recommendation: XAIFactor
    # True when these are real-time results from a live search (SerpApi)
    # rather than the seeded demo catalog — the frontend uses this to
    # switch labeling ("Live results" vs the catalog's usual framing) and
    # to know price_trend is always insufficient_data here, honestly.
    is_live: bool = False
