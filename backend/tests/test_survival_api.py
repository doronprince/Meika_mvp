import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.user import User
from tests.conftest import auth_headers


async def _db_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _make_user(**fields) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash", **fields)
        session.add(user)
        await session.commit()
        return user.id


async def _delete_users(*user_ids: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        for user_id in user_ids:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await session.commit()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_survival_and_income_routes_require_auth():
    async with _client() as client:
        assert (await client.post("/api/v1/survival/simulate", json={})).status_code == 401
        assert (await client.get("/api/v1/survival/presets")).status_code == 401
        assert (await client.get("/api/v1/income-streams")).status_code == 401


@pytest.mark.asyncio
async def test_income_stream_crud_is_tenant_scoped():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    owner, other = await _make_user(), await _make_user()
    try:
        async with _client() as client:
            created = await client.post(
                "/api/v1/income-streams",
                json={"label": "Cafe shifts", "kind": "part_time", "monthly_amount": "900000"},
                headers=auth_headers(owner),
            )
            assert created.status_code == 201
            stream_id = created.json()["id"]
            assert Decimal(created.json()["monthly_amount_krw_snapshot"]) == Decimal("900000.00")

            assert (await client.get("/api/v1/income-streams", headers=auth_headers(other))).json() == []
            foreign_patch = await client.patch(
                f"/api/v1/income-streams/{stream_id}", json={"monthly_amount": "1"}, headers=auth_headers(other)
            )
            assert foreign_patch.status_code == 404
            foreign_delete = await client.delete(f"/api/v1/income-streams/{stream_id}", headers=auth_headers(other))
            assert foreign_delete.status_code == 404

            patched = await client.patch(
                f"/api/v1/income-streams/{stream_id}", json={"monthly_amount": "1000000"}, headers=auth_headers(owner)
            )
            assert patched.status_code == 200
            assert Decimal(patched.json()["monthly_amount_krw_snapshot"]) == Decimal("1000000.00")

            assert (await client.delete(f"/api/v1/income-streams/{stream_id}", headers=auth_headers(owner))).status_code == 204
    finally:
        await _delete_users(owner, other)


@pytest.mark.asyncio
async def test_unsupported_income_currency_is_rejected():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    user_id = await _make_user()
    try:
        async with _client() as client:
            response = await client.post(
                "/api/v1/income-streams",
                json={"label": "Mystery", "kind": "other", "monthly_amount": "10", "currency": "XYZ"},
                headers=auth_headers(user_id),
            )
        assert response.status_code == 422
    finally:
        await _delete_users(user_id)


@pytest.mark.asyncio
async def test_simulate_without_savings_reports_needs_savings_and_savings_can_be_cleared():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    user_id = await _make_user()
    headers = auth_headers(user_id)
    try:
        async with _client() as client:
            response = await client.post("/api/v1/survival/simulate", json={}, headers=headers)
            assert response.status_code == 200
            body = response.json()
            assert body["state"] == "needs_savings"
            assert body["baseline_runway"] is None
            assert body["baseline"]["spend_source"] == "monthly_budget"

            set_savings = await client.patch("/api/v1/users/me", json={"liquid_savings_krw": "1500000"}, headers=headers)
            assert set_savings.status_code == 200
            assert Decimal(set_savings.json()["liquid_savings_krw"]) == Decimal("1500000")

            cleared = await client.patch("/api/v1/users/me", json={"liquid_savings_krw": None}, headers=headers)
            assert cleared.status_code == 200
            assert cleared.json()["liquid_savings_krw"] is None
    finally:
        await _delete_users(user_id)


@pytest.mark.asyncio
async def test_simulate_attributes_runway_loss_across_shocks():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    user_id = await _make_user(liquid_savings_krw=Decimal("2000000"))
    other_id = await _make_user()
    headers = auth_headers(user_id)
    today = date.today()
    try:
        async with _client() as client:
            stream = await client.post(
                "/api/v1/income-streams",
                json={"label": "Lab assistant", "kind": "part_time", "monthly_amount": "500000"},
                headers=headers,
            )
            assert stream.status_code == 201
            stream_id = stream.json()["id"]

            for days_ago, title, category, amount in (
                (40, "Rent", "housing_and_utilities", "450000"),
                (10, "Rent", "housing_and_utilities", "450000"),
                (5, "Groceries", "groceries", "80000"),
                (0, "Dinner", "cafes_and_dining", "30000"),
            ):
                created = await client.post(
                    "/api/v1/expenses",
                    json={
                        "title": title,
                        "category": category,
                        "amount_krw": amount,
                        "occurred_on": (today - timedelta(days=days_ago)).isoformat(),
                    },
                    headers=headers,
                )
                assert created.status_code == 201

            response = await client.post(
                "/api/v1/survival/simulate",
                json={
                    "shocks": [
                        {"kind": "income_loss", "pct": 100, "income_stream_id": stream_id},
                        {"kind": "one_off_expense", "amount_krw": 300000, "month": 1},
                    ]
                },
                headers=headers,
            )
            assert response.status_code == 200
            body = response.json()
            assert body["state"] == "computed"
            assert body["baseline"]["spend_source"] == "ledger"
            assert body["baseline"]["ledger_days"] == 41
            assert len(body["attributions"]) == 2
            assert abs(body["attribution_residual_months"]) < 1e-6
            shocked = body["shocked_runway"]["months"]
            baseline = body["baseline_runway"]["months"]
            assert shocked is not None and (baseline is None or shocked < baseline)
            assert all(f["detail"] for f in body["factors"])

            presets = await client.get("/api/v1/survival/presets", headers=headers)
            assert presets.status_code == 200
            assert "lose_largest_income" in {p["key"] for p in presets.json()}

            unknown_stream = await client.post(
                "/api/v1/survival/simulate",
                json={"shocks": [{"kind": "income_loss", "pct": 50, "income_stream_id": str(uuid.uuid4())}]},
                headers=headers,
            )
            assert unknown_stream.status_code == 422

            # Another user's stream id is just as unknown to this user.
            foreign = await client.post(
                "/api/v1/survival/simulate",
                json={"shocks": [{"kind": "income_loss", "pct": 50, "income_stream_id": stream_id}]},
                headers=auth_headers(other_id),
            )
            assert foreign.status_code == 422
    finally:
        await _delete_users(user_id, other_id)
