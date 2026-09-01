import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.ai import copilot_service
from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.enums import ChatRole
from app.models.user import User
from app.services import chat_service
from tests.conftest import auth_headers
from tests.test_live_price_service import _FakeAsyncClient


async def _db_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_chat_history_without_auth_header_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/copilot/history")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_history_with_invalid_token_is_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/copilot/history", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_history_empty_for_new_user():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        user_id = user.id

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/copilot/history", headers=auth_headers(user_id))

        assert response.status_code == 200
        assert response.json() == []
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()


@pytest.mark.asyncio
async def test_generate_reply_is_grounded_in_real_dashboard_numbers():
    """No LLM involved here (GEMINI_API_KEY is unset in test env) — this
    exercises the deterministic fallback that every reply falls back to,
    and asserts the xai_factors are the actual computed clarity-score
    factors, never fabricated text."""
    if not await _db_reachable():
        pytest.skip("database not reachable")

    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        user_id = user.id

    try:
        async with AsyncSessionLocal() as session:
            content, factors = await copilot_service.generate_reply(session, user_id, "how is my budget doing?")

        assert "Financial Clarity Score" in content
        assert "100" in content  # a brand-new user has no spend yet
        assert len(factors) == 3  # pace, projection, concentration — see dashboard_service
        assert all(factor.detail for factor in factors)

        async with AsyncSessionLocal() as session:
            saved = await chat_service.add_message(session, user_id, ChatRole.ASSISTANT, content, factors)
        assert saved.xai_factors is not None
        assert len(saved.xai_factors) == 3
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()


@pytest.mark.asyncio
async def test_generate_reply_answers_a_product_question_with_real_comparison():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    from datetime import datetime, timezone
    from decimal import Decimal

    from app.models.catalog import PriceQuote, Product, ProductListing, Store
    from app.models.enums import ExpenseCategory, StoreType, TransitMode

    product_name = f"Widgetronic {uuid.uuid4()}"
    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        store = Store(
            name=f"Test Store {uuid.uuid4()}",
            store_type=StoreType.ONLINE,
            location="Delivered",
            default_transit_mode=TransitMode.WALK,
            default_transit_cost_krw=Decimal("0"),
            rating=Decimal("4.5"),
        )
        product = Product(name=product_name, category=ExpenseCategory.ELECTRONICS)
        session.add_all([user, store, product])
        await session.flush()
        listing = ProductListing(product_id=product.id, store_id=store.id, price_krw=Decimal("9900"))
        session.add(listing)
        await session.flush()
        session.add(PriceQuote(listing_id=listing.id, price_krw=Decimal("9900"), observed_at=datetime.now(timezone.utc)))
        await session.commit()
        user_id, store_id, product_id = user.id, store.id, product.id

    try:
        async with AsyncSessionLocal() as session:
            content, factors = await copilot_service.generate_reply(session, user_id, "how much does Widgetronic cost?")

        assert product_name in content
        assert "9,900" in content  # the real seeded price, not a fabricated one
        assert len(factors) == 1
        assert "9,900" in factors[0].detail
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.execute(text("DELETE FROM products WHERE id = :id"), {"id": product_id})
            await session.execute(text("DELETE FROM stores WHERE id = :id"), {"id": store_id})
            await session.commit()


@pytest.mark.parametrize(
    "message,expected",
    [
        ("How much do wireless headphones cost?", True),
        ("What's the price of a laptop?", True),
        ("Is this a good buy?", True),
        ("How is my budget doing this month?", False),
        ("Thanks!", False),
    ],
)
def test_looks_like_price_question(message, expected):
    assert copilot_service._looks_like_price_question(message) is expected


@pytest.mark.parametrize(
    "message,expected_query",
    [
        ("How much do wireless headphones cost?", "wireless headphones"),
        ("What is the price of a laptop?", "a laptop"),
        ("how much does a bicycle cost", "a bicycle"),
    ],
)
def test_extract_product_query(message, expected_query):
    assert copilot_service._extract_product_query(message) == expected_query


@pytest.mark.asyncio
async def test_generate_reply_falls_back_to_budget_when_live_search_unavailable():
    """No catalog match and no SERPAPI_API_KEY (disabled for tests by the
    autouse fixture) -- must fall back to the budget answer, never crash or
    fabricate a price for a product it can't actually look up."""
    if not await _db_reachable():
        pytest.skip("database not reachable")

    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        user_id = user.id

    try:
        async with AsyncSessionLocal() as session:
            content, factors = await copilot_service.generate_reply(
                session, user_id, "How much do wireless headphones cost?"
            )

        assert "Financial Clarity Score" in content
        assert len(factors) == 3
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()


@pytest.mark.asyncio
async def test_generate_reply_uses_live_search_when_catalog_has_no_match(monkeypatch):
    if not await _db_reachable():
        pytest.skip("database not reachable")

    monkeypatch.setattr(settings, "serpapi_api_key", "fake-test-key")
    _FakeAsyncClient.payload = {
        "shopping_results": [
            {
                "title": "Test Wireless Headphones Pro",
                "source": "Test Electronics Store",
                "extracted_price": 49.99,
                "rating": 4.3,
                "product_link": "https://example.com/listing/headphones",
            },
        ]
    }
    import app.services.live_price_service as live_price_service

    monkeypatch.setattr(live_price_service.httpx, "AsyncClient", _FakeAsyncClient)

    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        user_id = user.id

    try:
        async with AsyncSessionLocal() as session:
            content, factors = await copilot_service.generate_reply(
                session, user_id, "How much do wireless headphones cost?"
            )

        assert content.startswith("Live result —")
        assert "Test Wireless Headphones Pro" in content
        assert "Test Electronics Store" in content
        assert len(factors) == 1
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()
