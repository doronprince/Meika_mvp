"""Seed the shared Seoul retail catalog (Store/Product/ProductListing/PriceQuote)
that the Price-Finder / True Economic Cost engine reads. This data isn't
user-owned — see [[tenant-isolation]] guardrail exemption in
app/models/catalog.py — so it's safe to wipe and re-seed freely.

Deliberately includes at least one product (Rice 10kg) where the cheapest
sticker price is NOT the cheapest True Economic Cost once transit is
factored in — that divergence is the entire point of the feature.

Usage:
    cd backend
    python -m scripts.seed_catalog
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.models.catalog import PriceQuote, Product, ProductListing, Store
from app.models.enums import ExpenseCategory, StoreType, TransitMode

STORES = {
    "emart": dict(
        name="Emart Yeoksam",
        store_type=StoreType.LOCAL_SUPERMARKET,
        location="Yeoksam-dong, Gangnam-gu",
        default_transit_mode=TransitMode.SUBWAY_BUS,
        default_transit_cost_krw=Decimal("1350"),
        rating=Decimal("4.5"),
    ),
    "homeplus": dict(
        name="Homeplus Express Sillim",
        store_type=StoreType.LOCAL_SUPERMARKET,
        location="Sillim-dong, Gwanak-gu",
        default_transit_mode=TransitMode.SUBWAY_BUS,
        default_transit_cost_krw=Decimal("1350"),
        rating=Decimal("4.2"),
    ),
    "gs25": dict(
        name="GS25 Sinchon",
        store_type=StoreType.CONVENIENCE_STORE,
        location="Sinchon-dong, Seodaemun-gu",
        default_transit_mode=TransitMode.WALK,
        default_transit_cost_krw=Decimal("0"),
        rating=Decimal("4.0"),
    ),
    "gyeongdong": dict(
        name="Gyeongdong Traditional Market",
        store_type=StoreType.TRADITIONAL_MARKET,
        location="Jegi-dong, Dongdaemun-gu",
        default_transit_mode=TransitMode.TAXI,
        default_transit_cost_krw=Decimal("8500"),
        rating=Decimal("4.7"),
    ),
    "coupang": dict(
        name="Coupang (Online)",
        store_type=StoreType.ONLINE,
        location="Nationwide delivery",
        default_transit_mode=TransitMode.WALK,
        default_transit_cost_krw=Decimal("0"),
        rating=Decimal("4.6"),
    ),
}

# price_history: list of (days_ago, price_krw), oldest first. A single entry
# means "insufficient data" for a trend — deliberately used for the
# traditional market, where prices aren't tracked as rigorously.
PRODUCTS = [
    dict(
        name="Rice 10kg",
        category=ExpenseCategory.GROCERIES,
        listings=[
            dict(store="emart", price="24000", history=[(21, "22000"), (14, "23000"), (0, "24000")]),
            dict(store="homeplus", price="22500", history=[(21, "22400"), (14, "22600"), (0, "22500")]),
            dict(store="coupang", price="23500", history=[(21, "25000"), (14, "24000"), (0, "23500")]),
            dict(store="gyeongdong", price="21000", history=[(0, "21000")]),
        ],
    ),
    dict(
        name="Instant Ramen (5-pack)",
        category=ExpenseCategory.GROCERIES,
        listings=[
            dict(store="emart", price="4200", history=[(21, "4100"), (14, "4150"), (0, "4200")]),
            dict(store="homeplus", price="3900", history=[(21, "4300"), (14, "4100"), (0, "3900")]),
            dict(store="gs25", price="5500", history=[(21, "5400"), (14, "5500"), (0, "5500")]),
            dict(store="coupang", price="4000", history=[(21, "3700"), (14, "3850"), (0, "4000")]),
        ],
    ),
    dict(
        name="Milk 1L",
        category=ExpenseCategory.GROCERIES,
        listings=[
            dict(store="emart", price="2800", history=[(14, "2750"), (0, "2800")]),
            dict(store="homeplus", price="2700", history=[(14, "2700"), (0, "2700")]),
            dict(store="gs25", price="3200", history=[(14, "3100"), (0, "3200")]),
        ],
    ),
    dict(
        name="Laundry Detergent 3L",
        category=ExpenseCategory.HOUSING_AND_UTILITIES,
        listings=[
            dict(store="emart", price="15000", history=[(21, "15100"), (14, "15000"), (0, "15000")]),
            dict(store="coupang", price="14500", history=[(21, "16000"), (14, "15200"), (0, "14500")]),
            dict(store="homeplus", price="15500", history=[(21, "14800"), (14, "15200"), (0, "15500")]),
        ],
    ),
    dict(
        name="USB-C Charging Cable",
        category=ExpenseCategory.ELECTRONICS,
        listings=[
            dict(store="coupang", price="8900", history=[(21, "10500"), (14, "9700"), (0, "8900")]),
            dict(store="emart", price="12000", history=[(21, "12000"), (14, "12000"), (0, "12000")]),
            dict(store="gs25", price="15000", history=[(14, "15000"), (0, "15000")]),
        ],
    ),
]


async def seed() -> None:
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Product))
        await session.execute(delete(Store))
        await session.flush()

        stores = {key: Store(**data) for key, data in STORES.items()}
        session.add_all(stores.values())
        await session.flush()

        listing_count = 0
        for product_data in PRODUCTS:
            product = Product(name=product_data["name"], category=product_data["category"])
            session.add(product)
            await session.flush()

            for listing_data in product_data["listings"]:
                listing = ProductListing(
                    product_id=product.id,
                    store_id=stores[listing_data["store"]].id,
                    price_krw=Decimal(listing_data["price"]),
                )
                session.add(listing)
                await session.flush()
                listing_count += 1

                for days_ago, price in listing_data["history"]:
                    session.add(
                        PriceQuote(
                            listing_id=listing.id,
                            price_krw=Decimal(price),
                            observed_at=now - timedelta(days=days_ago),
                        )
                    )

        await session.commit()
        print(f"Seeded {len(stores)} stores, {len(PRODUCTS)} products, {listing_count} listings.")


if __name__ == "__main__":
    asyncio.run(seed())
