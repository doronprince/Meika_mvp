import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.catalog import PriceQuote, Product, ProductListing, Store
from app.models.enums import ExpenseCategory, StoreType, TransitMode
from app.models.user import User
from app.services.fx_service import FRANKFURTER_BASE_URL
from tests.conftest import auth_headers


async def _db_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _fx_api_reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{FRANKFURTER_BASE_URL}/latest", params={"from": "KRW"})
            return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.asyncio
async def test_search_with_no_query_does_not_error():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/price-finder/search")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_search_for_unknown_product_returns_empty_list():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/price-finder/search", params={"q": f"nonexistent-{uuid.uuid4()}"}
        )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_true_economic_cost_can_beat_a_lower_sticker_price():
    """The whole point of the engine: a cheaper listed price at a store with
    expensive transit can lose to a pricier-but-closer/cheaper-transit store
    once True Economic Cost is computed."""
    if not await _db_reachable():
        pytest.skip("database not reachable")

    product_name = f"Test Widget {uuid.uuid4()}"
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        far_store = Store(
            name=f"Far Cheap Store {uuid.uuid4()}",
            store_type=StoreType.TRADITIONAL_MARKET,
            location="Far away",
            default_transit_mode=TransitMode.TAXI,
            default_transit_cost_krw=Decimal("8500"),
            rating=Decimal("4.0"),
        )
        near_store = Store(
            name=f"Near Pricier Store {uuid.uuid4()}",
            store_type=StoreType.ONLINE,
            location="Delivered",
            default_transit_mode=TransitMode.WALK,
            default_transit_cost_krw=Decimal("0"),
            rating=Decimal("4.5"),
        )
        product = Product(name=product_name, category=ExpenseCategory.GROCERIES)
        session.add_all([far_store, near_store, product])
        await session.flush()

        cheap_listing = ProductListing(product_id=product.id, store_id=far_store.id, price_krw=Decimal("21000"))
        pricier_listing = ProductListing(product_id=product.id, store_id=near_store.id, price_krw=Decimal("23500"))
        session.add_all([cheap_listing, pricier_listing])
        await session.flush()
        session.add(PriceQuote(listing_id=cheap_listing.id, price_krw=Decimal("21000"), observed_at=now))
        session.add(PriceQuote(listing_id=pricier_listing.id, price_krw=Decimal("23500"), observed_at=now))
        await session.commit()

        store_ids = [far_store.id, near_store.id]
        product_id = product.id

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/price-finder/search", params={"q": product_name})

        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        result = results[0]
        comparisons = result["comparisons"]
        assert len(comparisons) == 2

        # Sorted by True Economic Cost ascending — the near/pricier store
        # (23500 + 0 transit = 23500) beats the far/cheap store
        # (21000 + 8500 transit = 29500) despite its higher sticker price.
        assert comparisons[0]["store_name"].startswith("Near Pricier Store")
        assert Decimal(str(comparisons[0]["true_economic_cost_krw"])) == Decimal("23500.00")
        assert comparisons[1]["store_name"].startswith("Far Cheap Store")
        assert Decimal(str(comparisons[1]["true_economic_cost_krw"])) == Decimal("29500.00")

        assert "True cost beats sticker price" in result["recommendation"]["label"]
        assert "21,000" in result["recommendation"]["detail"]
        assert "29,500" in result["recommendation"]["detail"]
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM products WHERE id = :id"), {"id": product_id})
            for store_id in store_ids:
                await session.execute(text("DELETE FROM stores WHERE id = :id"), {"id": store_id})
            await session.commit()


@pytest.mark.asyncio
async def test_price_trend_is_computed_from_history_not_asserted():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    product_name = f"Test Trend Widget {uuid.uuid4()}"
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        store = Store(
            name=f"Trend Store {uuid.uuid4()}",
            store_type=StoreType.LOCAL_SUPERMARKET,
            location="Somewhere",
            default_transit_mode=TransitMode.WALK,
            default_transit_cost_krw=Decimal("0"),
            rating=Decimal("4.0"),
        )
        product = Product(name=product_name, category=ExpenseCategory.GROCERIES)
        session.add_all([store, product])
        await session.flush()

        rising_listing = ProductListing(product_id=product.id, store_id=store.id, price_krw=Decimal("10000"))
        session.add(rising_listing)
        await session.flush()
        session.add_all(
            [
                PriceQuote(listing_id=rising_listing.id, price_krw=Decimal("8000"), observed_at=now - timedelta(days=14)),
                PriceQuote(listing_id=rising_listing.id, price_krw=Decimal("10000"), observed_at=now),
            ]
        )
        await session.commit()

        store_id = store.id
        product_id = product.id

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/price-finder/search", params={"q": product_name})

        assert response.status_code == 200
        comparisons = response.json()[0]["comparisons"]
        assert comparisons[0]["price_trend"] == "rising"
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM products WHERE id = :id"), {"id": product_id})
            await session.execute(text("DELETE FROM stores WHERE id = :id"), {"id": store_id})
            await session.commit()


@pytest.mark.asyncio
async def test_recommendation_prose_respects_signed_in_users_currency():
    """Same gap as the dashboard's clarity-score factors: the recommendation
    `detail` is prose generated server-side, not a numeric field the
    frontend converts -- it must follow preferred_currency when the caller
    is signed in, and stay KRW for anonymous callers (the catalog itself
    isn't tenant-owned)."""
    if not await _db_reachable():
        pytest.skip("database not reachable")
    if not await _fx_api_reachable():
        pytest.skip("live FX API not reachable")

    product_name = f"Test Currency Widget {uuid.uuid4()}"
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        far_store = Store(
            name=f"Far Cheap Store {uuid.uuid4()}",
            store_type=StoreType.TRADITIONAL_MARKET,
            location="Far away",
            default_transit_mode=TransitMode.TAXI,
            default_transit_cost_krw=Decimal("8500"),
            rating=Decimal("4.0"),
        )
        near_store = Store(
            name=f"Near Pricier Store {uuid.uuid4()}",
            store_type=StoreType.ONLINE,
            location="Delivered",
            default_transit_mode=TransitMode.WALK,
            default_transit_cost_krw=Decimal("0"),
            rating=Decimal("4.5"),
        )
        product = Product(name=product_name, category=ExpenseCategory.GROCERIES)
        session.add_all([user, far_store, near_store, product])
        await session.flush()

        cheap_listing = ProductListing(product_id=product.id, store_id=far_store.id, price_krw=Decimal("21000"))
        pricier_listing = ProductListing(product_id=product.id, store_id=near_store.id, price_krw=Decimal("23500"))
        session.add_all([cheap_listing, pricier_listing])
        await session.flush()
        session.add(PriceQuote(listing_id=cheap_listing.id, price_krw=Decimal("21000"), observed_at=now))
        session.add(PriceQuote(listing_id=pricier_listing.id, price_krw=Decimal("23500"), observed_at=now))
        await session.commit()

        user_id, store_ids, product_id = user.id, [far_store.id, near_store.id], product.id

    headers = auth_headers(user_id)
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            patch_response = await client.patch(
                "/api/v1/users/me", json={"preferred_currency": "usd"}, headers=headers
            )
            assert patch_response.status_code == 200

            authed_response = await client.get(
                "/api/v1/price-finder/search", params={"q": product_name}, headers=headers
            )
            anon_response = await client.get("/api/v1/price-finder/search", params={"q": product_name})

        authed_detail = authed_response.json()[0]["recommendation"]["detail"]
        assert "$" in authed_detail
        assert "₩" not in authed_detail

        anon_detail = anon_response.json()[0]["recommendation"]["detail"]
        assert "₩" in anon_detail
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.execute(text("DELETE FROM products WHERE id = :id"), {"id": product_id})
            for store_id in store_ids:
                await session.execute(text("DELETE FROM stores WHERE id = :id"), {"id": store_id})
            await session.commit()
