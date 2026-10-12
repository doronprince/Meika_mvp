import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.user import User
from app.services.fx_service import FRANKFURTER_BASE_URL
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


async def _fx_api_reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{FRANKFURTER_BASE_URL}/latest", params={"from": "KRW"})
            return response.status_code == 200
    except httpx.HTTPError:
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


@pytest.mark.asyncio
async def test_clarity_score_factor_prose_respects_preferred_currency():
    """The factor `detail` strings are prose the backend generates, not a
    numeric field the frontend converts itself -- this pins the fix for
    that gap: they must render in the user's preferred_currency, not a
    hardcoded ₩, once one is set."""
    if not await _db_reachable():
        pytest.skip("database not reachable")
    if not await _fx_api_reachable():
        pytest.skip("live FX API not reachable")

    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        user_id = user.id

    headers = auth_headers(user_id)
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            patch_response = await client.patch(
                "/api/v1/users/me", json={"preferred_currency": "usd"}, headers=headers
            )
            assert patch_response.status_code == 200

            create_response = await client.post("/api/v1/expenses", json=EXPENSE_PAYLOAD, headers=headers)
            assert create_response.status_code == 201

            response = await client.get("/api/v1/dashboard/summary", headers=headers)

        assert response.status_code == 200
        body = response.json()
        details = " ".join(f["detail"] for f in body["clarity_score"]["factors"])
        assert "$" in details
        assert "₩" not in details
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()


# --- month-end projection: commitments once, variable spend as a rate ---
# [[recurring-is-not-a-rate]]. Pure function, no database.

from types import SimpleNamespace  # noqa: E402

from app.models.enums import ExpenseCategory as _Category  # noqa: E402
from app.services.dashboard_service import project_month_end  # noqa: E402


def _expense(day: date, amount: str, category=_Category.GROCERIES, store="Emart"):
    return SimpleNamespace(
        occurred_on=day,
        amount_krw=Decimal(amount),
        transit_cost_krw=Decimal("0"),
        category=category,
        store_name=store,
        title=store,
    )


def _rent_and_coffee_history():
    rent = [_expense(date(2026, m, 1), "500000", _Category.HOUSING_AND_UTILITIES, "Studio") for m in (6, 7, 8, 9)]
    coffee = [_expense(date(2026, m, d), "10000") for m in (6, 7, 8, 9) for d in range(1, 29)]
    return rent + coffee


def test_rent_is_counted_once_instead_of_extrapolated_all_month():
    history = _rent_and_coffee_history()
    this_month = [_expense(date(2026, 10, 1), "500000", _Category.HOUSING_AND_UTILITIES, "Studio")]
    this_month += [_expense(date(2026, 10, d), "10000") for d in range(1, 11)]

    projection = project_month_end(
        this_month=this_month, history=history, today=date(2026, 10, 10), days_in_month=31
    )

    # Rent once (₩500,000) plus ₩10,000/day of variable spending over 31 days.
    assert projection.total == Decimal("810000.00")
    assert projection.recurring == Decimal("500000.00")
    assert projection.variable_per_day == Decimal("10000.00")
    # The old flat-rate formula read ₩1,860,000 — a breach of a ₩1M budget
    # every month, caused by the rent alone.
    naive = (sum(e.amount_krw for e in this_month) / Decimal(10) * Decimal(31)).quantize(Decimal("0.01"))
    assert naive == Decimal("1860000.00")


def test_a_shop_visited_often_is_variable_spending_not_a_commitment():
    projection = project_month_end(
        this_month=[_expense(date(2026, 10, d), "10000") for d in range(1, 11)],
        history=_rent_and_coffee_history(),
        today=date(2026, 10, 10),
        days_in_month=31,
    )
    # Only the rent qualifies, even though the shop appears in every month.
    assert projection.commitment_count == 1
    assert projection.variable_per_day == Decimal("10000.00")


def test_a_commitment_not_yet_paid_is_still_expected_this_month():
    history = [_expense(date(2026, m, 25), "300000", _Category.HOUSING_AND_UTILITIES, "Studio") for m in (6, 7, 8, 9)]
    projection = project_month_end(
        this_month=[], history=history, today=date(2026, 10, 10), days_in_month=31
    )
    assert projection.recurring == Decimal("300000.00")


def test_a_new_user_with_no_history_still_gets_the_simple_rate():
    this_month = [_expense(date(2026, 10, d), "10000") for d in range(1, 11)]
    projection = project_month_end(this_month=this_month, history=[], today=date(2026, 10, 10), days_in_month=31)

    assert projection.commitment_count == 0
    assert projection.total == Decimal("310000.00")


def test_projection_is_withheld_in_the_first_week():
    assert project_month_end(this_month=[], history=[], today=date(2026, 10, 3), days_in_month=31) is None
