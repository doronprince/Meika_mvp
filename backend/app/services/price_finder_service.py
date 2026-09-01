import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Product, ProductListing
from app.models.user import User
from app.schemas.common import PriceTrendResult, XAIFactor
from app.schemas.price_finder import PriceFinderResult, StoreComparison
from app.services.currency_display import DisplayCurrency, resolve_display_currency

# A price move smaller than this is noise, not a trend — see
# [[dashboard-projection-warmup]] for the same "don't overstate a small
# sample" principle applied to the Financial Clarity Score.
TREND_THRESHOLD = Decimal("0.03")

_CENTS = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _compute_trend(listing: ProductListing) -> PriceTrendResult:
    history = listing.price_history
    if len(history) < 2:
        return PriceTrendResult.INSUFFICIENT_DATA

    first, last = history[0].price_krw, history[-1].price_krw
    if first == 0:
        return PriceTrendResult.STABLE

    change_ratio = (last - first) / first
    if change_ratio > TREND_THRESHOLD:
        return PriceTrendResult.RISING
    if change_ratio < -TREND_THRESHOLD:
        return PriceTrendResult.FALLING
    return PriceTrendResult.STABLE


def _build_comparison(listing: ProductListing) -> StoreComparison:
    store = listing.store
    true_cost = _q2(listing.price_krw + store.default_transit_cost_krw)
    return StoreComparison(
        store_id=store.id,
        store_name=store.name,
        store_type=store.store_type,
        price_krw=listing.price_krw,
        transit_cost_krw=store.default_transit_cost_krw,
        transit_mode=store.default_transit_mode,
        true_economic_cost_krw=true_cost,
        price_trend=_compute_trend(listing),
        rating=store.rating,
        in_stock=listing.in_stock,
    )


def _build_recommendation(comparisons: list[StoreComparison], display: DisplayCurrency) -> XAIFactor:
    in_stock = [c for c in comparisons if c.in_stock] or comparisons
    cheapest_true_cost = min(in_stock, key=lambda c: c.true_economic_cost_krw)
    cheapest_sticker = min(in_stock, key=lambda c: c.price_krw)

    if cheapest_true_cost.store_id == cheapest_sticker.store_id:
        return XAIFactor(
            label=f"Best overall value: {cheapest_true_cost.store_name}",
            detail=(
                f"{cheapest_true_cost.store_name} has both the lowest price "
                f"({display.format(cheapest_true_cost.price_krw)}) "
                f"and the lowest True Economic Cost after {display.format(cheapest_true_cost.transit_cost_krw)} "
                f"transit: {display.format(cheapest_true_cost.true_economic_cost_krw)}."
            ),
            value=float(cheapest_true_cost.true_economic_cost_krw),
        )

    sticker_total_at_cheapest_sticker = cheapest_sticker.true_economic_cost_krw
    return XAIFactor(
        label=f"True cost beats sticker price: {cheapest_true_cost.store_name}",
        detail=(
            f"{cheapest_sticker.store_name} looks cheapest at {display.format(cheapest_sticker.price_krw)}, but "
            f"after {display.format(cheapest_sticker.transit_cost_krw)} transit its True Economic Cost is "
            f"{display.format(sticker_total_at_cheapest_sticker)}. {cheapest_true_cost.store_name} is actually "
            f"lower overall at {display.format(cheapest_true_cost.true_economic_cost_krw)} "
            f"({display.format(cheapest_true_cost.price_krw)} + "
            f"{display.format(cheapest_true_cost.transit_cost_krw)} transit)."
        ),
        value=float(cheapest_true_cost.true_economic_cost_krw),
    )


async def search_price_comparisons(
    db: AsyncSession, query: str | None, user_id: uuid.UUID | None = None
) -> list[PriceFinderResult]:
    display = DisplayCurrency("KRW", Decimal("1"))
    if user_id is not None:
        user = await db.get(User, user_id)
        if user is not None:
            display = await resolve_display_currency(user.preferred_currency)

    stmt = (
        select(Product)
        .options(
            selectinload(Product.listings).selectinload(ProductListing.store),
            selectinload(Product.listings).selectinload(ProductListing.price_history),
        )
        .order_by(Product.name)
    )
    if query:
        stmt = stmt.where(Product.name.ilike(f"%{query}%"))

    products = (await db.execute(stmt)).scalars().unique().all()

    results: list[PriceFinderResult] = []
    for product in products:
        if not product.listings:
            continue
        comparisons = sorted(
            (_build_comparison(listing) for listing in product.listings),
            key=lambda c: c.true_economic_cost_krw,
        )
        results.append(
            PriceFinderResult(
                product_id=product.id,
                product_name=product.name,
                category=product.category,
                comparisons=comparisons,
                recommendation=_build_recommendation(comparisons, display),
            )
        )
    return results
