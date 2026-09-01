import uuid

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


@pytest.mark.asyncio
async def test_get_profile_without_auth_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/users/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_profile_defaults_to_krw_and_can_change_currency():
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
            get_response = await client.get("/api/v1/users/me", headers=headers)
            assert get_response.status_code == 200
            assert get_response.json()["preferred_currency"] == "KRW"

            patch_response = await client.patch(
                "/api/v1/users/me", json={"preferred_currency": "eur"}, headers=headers
            )
            assert patch_response.status_code == 200
            assert patch_response.json()["preferred_currency"] == "EUR"

            bad_currency_response = await client.patch(
                "/api/v1/users/me", json={"preferred_currency": "XXX"}, headers=headers
            )
            assert bad_currency_response.status_code == 422
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()
