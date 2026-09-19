import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.enums import ExpenseCategory, ExposureKind
from app.models.expense import Expense
from app.models.exposure import ExposureSession
from app.models.user import User
from tests.conftest import auth_headers


async def _db_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _make_user() -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        return user.id


async def _delete_users(*user_ids: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        for user_id in user_ids:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await session.commit()


@pytest.mark.asyncio
async def test_exposure_routes_require_auth():
    async with _client() as client:
        assert (await client.get("/api/v1/exposure/insights")).status_code == 401
        assert (await client.get("/api/v1/exposure/sessions")).status_code == 401


@pytest.mark.asyncio
async def test_session_logging_validation_and_tenant_scoping():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    owner, other = await _make_user(), await _make_user()
    today = date.today()
    try:
        async with _client() as client:
            created = await client.post(
                "/api/v1/exposure/sessions",
                json={"occurred_on": today.isoformat(), "platform": "Instagram", "kind": "social_feed", "minutes": 45},
                headers=auth_headers(owner),
            )
            assert created.status_code == 201
            session_id = created.json()["id"]

            future = await client.post(
                "/api/v1/exposure/sessions",
                json={"occurred_on": (today + timedelta(days=1)).isoformat(), "platform": "X", "kind": "other", "minutes": 5},
                headers=auth_headers(owner),
            )
            assert future.status_code == 422
            zero = await client.post(
                "/api/v1/exposure/sessions",
                json={"occurred_on": today.isoformat(), "platform": "X", "kind": "other", "minutes": 0},
                headers=auth_headers(owner),
            )
            assert zero.status_code == 422

            assert (await client.get("/api/v1/exposure/sessions", headers=auth_headers(other))).json() == []
            foreign_delete = await client.delete(f"/api/v1/exposure/sessions/{session_id}", headers=auth_headers(other))
            assert foreign_delete.status_code == 404

            listed = await client.get("/api/v1/exposure/sessions", headers=auth_headers(owner))
            assert [s["id"] for s in listed.json()] == [session_id]
            deleted = await client.delete(f"/api/v1/exposure/sessions/{session_id}", headers=auth_headers(owner))
            assert deleted.status_code == 204
    finally:
        await _delete_users(owner, other)


@pytest.mark.asyncio
async def test_insights_blackout_then_computed():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    fresh, seasoned = await _make_user(), await _make_user()
    today = date.today()
    rng = random.Random(4)
    async with AsyncSessionLocal() as session:
        for offset in range(50):
            day = today - timedelta(days=offset)
            minutes = rng.choice([0, 0, 30, 60, 120])
            if minutes:
                session.add(ExposureSession(user_id=seasoned, occurred_on=day, platform="Coupang",
                                            kind=ExposureKind.SHOPPING_APP, minutes=minutes))
            session.add(Expense(user_id=seasoned, title="Coffee", category=ExpenseCategory.CAFES_AND_DINING,
                                amount_krw=Decimal(rng.randint(3, 9) * 1000), occurred_on=day))
        await session.commit()

    try:
        async with _client() as client:
            blank = await client.get("/api/v1/exposure/insights", headers=auth_headers(fresh))
            scored = await client.get("/api/v1/exposure/insights", headers=auth_headers(seasoned))

        assert blank.status_code == 200
        assert blank.json()["state"] == "insufficient_data"
        assert blank.json()["intervention"]["triggered"] is False

        assert scored.status_code == 200
        body = scored.json()
        assert body["state"] == "computed"
        assert body["primary"]["n_permutations"] > 0
        assert body["verdict"] in ("association", "no_clear_association")
        assert [lag["lag_days"] for lag in body["exploratory_lags"]] == [0, 1, 2]
        assert all(f["detail"] for f in body["factors"])
    finally:
        await _delete_users(fresh, seasoned)
