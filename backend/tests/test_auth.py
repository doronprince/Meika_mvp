import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal, engine
from app.main import app


async def _db_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_register_rejects_short_password():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": f"{uuid.uuid4()}@example.com", "password": "short"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_malformed_email():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "a-real-password"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_login_and_use_token_round_trip():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    email = f"{uuid.uuid4()}@example.com"
    password = "a-secure-password-123"
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            register_response = await client.post(
                "/api/v1/auth/register", json={"email": email, "password": password}
            )
            assert register_response.status_code == 201
            token_body = register_response.json()
            assert token_body["token_type"] == "bearer"
            user_id = token_body["user_id"]
            assert decode_access_token(token_body["access_token"]) == uuid.UUID(user_id)

            # Duplicate registration is rejected.
            duplicate_response = await client.post(
                "/api/v1/auth/register", json={"email": email, "password": password}
            )
            assert duplicate_response.status_code == 409

            # Wrong password is rejected.
            bad_login_response = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
            )
            assert bad_login_response.status_code == 401

            # Correct password logs in and the token works against a real endpoint.
            login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
            assert login_response.status_code == 200
            access_token = login_response.json()["access_token"]

            summary_response = await client.get(
                "/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {access_token}"}
            )
            assert summary_response.status_code == 200
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
            await session.commit()


@pytest.mark.asyncio
async def test_login_rate_limit_kicks_in_after_configured_threshold():
    """Sliding-window limiter on /auth/* — see app/core/config.py's
    auth_rate_limit_per_minute (10 by default). Doesn't need the DB: a 401
    for bad credentials still counts against the limit."""
    from app.core.config import settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        statuses = []
        for _ in range(settings.auth_rate_limit_per_minute + 3):
            response = await client.post(
                "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
            )
            statuses.append(response.status_code)

    assert 429 in statuses
