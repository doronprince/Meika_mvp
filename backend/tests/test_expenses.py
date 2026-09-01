import uuid

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.user import User
from app.services.fx_service import FRANKFURTER_BASE_URL
from tests.conftest import auth_headers

VALID_PAYLOAD = {
    "title": "Groceries at Emart",
    "category": "groceries",
    "amount_krw": "35000",
    "transit_cost_krw": "1500",
    "transit_mode": "subway_bus",
    "occurred_on": "2026-08-01",
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
async def test_create_expense_without_auth_header_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/expenses", json=VALID_PAYLOAD)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_expense_with_invalid_token_is_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/expenses", json=VALID_PAYLOAD, headers={"Authorization": "Bearer not-a-real-token"}
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_expense_rejects_non_positive_amount():
    transport = ASGITransport(app=app)
    payload = {**VALID_PAYLOAD, "amount_krw": "0"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/expenses", json=payload, headers=auth_headers(uuid.uuid4()))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_expense_rejects_unknown_category():
    transport = ASGITransport(app=app)
    payload = {**VALID_PAYLOAD, "category": "not_a_real_category"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/expenses", json=payload, headers=auth_headers(uuid.uuid4()))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_expense_rejects_neither_amount_source():
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "amount_krw"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/expenses", json=payload, headers=auth_headers(uuid.uuid4()))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_expense_rejects_both_amount_sources():
    payload = {**VALID_PAYLOAD, "foreign_amount": "10", "foreign_currency": "usd"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/expenses", json=payload, headers=auth_headers(uuid.uuid4()))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_expense_rejects_unsupported_foreign_currency():
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "amount_krw"}
    payload.update(foreign_amount="10", foreign_currency="xxx")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/expenses", json=payload, headers=auth_headers(uuid.uuid4()))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_expense_with_foreign_currency_converts_via_live_rate():
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
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "amount_krw"}
    payload.update(foreign_amount="10.00", foreign_currency="usd")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/expenses", json=payload, headers=headers)

        assert response.status_code == 201
        body = response.json()
        assert body["original_currency"] == "USD"
        assert float(body["original_amount"]) == 10.0
        # $10 should be somewhere in the thousands of KRW, not equal to the
        # raw figure -- proves a real conversion happened, not a passthrough.
        assert float(body["amount_krw"]) > 1000
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()


@pytest.mark.asyncio
async def test_expense_crud_round_trip():
    """End-to-end against a real database. Skipped when Postgres isn't reachable
    (e.g. `docker compose up postgres` hasn't been run) — mirrors the tolerance
    the health check itself applies to a missing database."""
    if not await _db_reachable():
        pytest.skip("database not reachable")

    # expenses.user_id is a NOT NULL FK into users — a random UUID with no
    # matching row would fail the insert with an IntegrityError, not exercise
    # the CRUD path.
    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        user_id = user.id

    headers = auth_headers(user_id)
    transport = ASGITransport(app=app)

    try:
        await _run_crud_round_trip(transport, headers)
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()


async def _run_crud_round_trip(transport, headers):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post("/api/v1/expenses", json=VALID_PAYLOAD, headers=headers)
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["total_economic_cost_krw"] == "36500.00" or created["total_economic_cost_krw"] == 36500.0
        expense_id = created["id"]

        list_response = await client.get("/api/v1/expenses", headers=headers)
        assert list_response.status_code == 200
        assert any(item["id"] == expense_id for item in list_response.json())

        get_response = await client.get(f"/api/v1/expenses/{expense_id}", headers=headers)
        assert get_response.status_code == 200

        other_user_response = await client.get(
            f"/api/v1/expenses/{expense_id}", headers=auth_headers(uuid.uuid4())
        )
        assert other_user_response.status_code == 404

        update_response = await client.patch(
            f"/api/v1/expenses/{expense_id}", json={"amount_krw": "40000"}, headers=headers
        )
        assert update_response.status_code == 200
        assert float(update_response.json()["amount_krw"]) == 40000.0

        delete_response = await client.delete(f"/api/v1/expenses/{expense_id}", headers=headers)
        assert delete_response.status_code == 204

        missing_response = await client.get(f"/api/v1/expenses/{expense_id}", headers=headers)
        assert missing_response.status_code == 404
