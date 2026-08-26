import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.user import User
from tests.conftest import auth_headers

EXPENSE_PAYLOAD = {
    "title": "Groceries at Emart",
    "category": "groceries",
    "amount_krw": "35000",
    "transit_cost_krw": "1500",
    "transit_mode": "subway_bus",
    "occurred_on": date.today().isoformat(),
}

SECOND_EXPENSE_PAYLOAD = {
    "title": "Coffee",
    "category": "cafes_and_dining",
    "amount_krw": "6000",
    "transit_cost_krw": "0",
    "transit_mode": "walk",
    "occurred_on": date.today().isoformat(),
}


async def _db_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_dashboard_summary_without_auth_header_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard/summary")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_summary_with_invalid_token_is_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/dashboard/summary", headers={"Authorization": "Bearer not-a-real-token"}
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_summary_for_unknown_user_is_not_found():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard/summary", headers=auth_headers(uuid.uuid4()))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_summary_empty_state_has_no_fabricated_numbers():
    """A user with zero expenses this month should get a fully computed
    zero/neutral summary, not an error — this is the state every new user
    sees."""
    if not await _db_reachable():
        pytest.skip("database not reachable")

    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        user_id = user.id
        budget = user.monthly_budget_krw

    headers = auth_headers(user_id)
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/dashboard/summary", headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert Decimal(str(body["total_spent_this_month_krw"])) == Decimal("0.00")
        assert Decimal(str(body["remaining_budget_krw"])) == budget
        assert body["category_breakdown"] == []
        assert body["clarity_score"]["value"] == 100
        assert body["clarity_score"]["risk_level"] == "low"
        assert len(body["clarity_score"]["factors"]) == 3
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()


@pytest.mark.asyncio
async def test_dashboard_summary_reflects_logged_expenses():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        user_id = user.id

    headers = auth_headers(user_id)
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for payload in (EXPENSE_PAYLOAD, SECOND_EXPENSE_PAYLOAD):
                create_response = await client.post("/api/v1/expenses", json=payload, headers=headers)
                assert create_response.status_code == 201

            response = await client.get("/api/v1/dashboard/summary", headers=headers)

        assert response.status_code == 200
        body = response.json()

        expected_total = Decimal("35000") + Decimal("1500") + Decimal("6000") + Decimal("0")
        assert Decimal(str(body["total_spent_this_month_krw"])) == expected_total

        category_total = sum(
            Decimal(str(item["total_krw"])) for item in body["category_breakdown"]
        )
        assert category_total == expected_total
        assert {item["category"] for item in body["category_breakdown"]} == {
            "groceries",
            "cafes_and_dining",
        }

        days_elapsed = date.today().day
        expected_velocity = (expected_total / Decimal(days_elapsed)).quantize(Decimal("0.01"))
        assert Decimal(str(body["spending_velocity_krw_per_day"])) == expected_velocity

        if days_elapsed >= 7:
            assert body["projected_month_end_spend_krw"] is not None
        else:
            assert body["projected_month_end_spend_krw"] is None

        assert len(body["clarity_score"]["factors"]) == 3
        assert 0 <= body["clarity_score"]["value"] <= 100
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()
