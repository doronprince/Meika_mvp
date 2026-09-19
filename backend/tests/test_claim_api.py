import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.user import User
from app.services import claim_check_service, claim_search
from app.services.claim_sources import SearchHit
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


async def _cleanup(*user_ids: uuid.UUID, query_hashes: tuple[str, ...] = ()) -> None:
    async with AsyncSessionLocal() as session:
        for user_id in user_ids:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        for h in query_hashes:
            await session.execute(text("DELETE FROM claim_evidence_cache WHERE query_hash = :h"), {"h": h})
        await session.commit()


@pytest.mark.asyncio
async def test_claim_routes_require_auth():
    async with _client() as client:
        assert (await client.post("/api/v1/claim-check/evaluate", json={"claim_text": "x" * 20})).status_code == 401
        assert (await client.get("/api/v1/claim-check/history")).status_code == 401


@pytest.mark.asyncio
async def test_without_search_key_the_evaluation_degrades_and_is_tenant_scoped():
    if not await _db_reachable():
        pytest.skip("database not reachable")
    owner, other = await _make_user(), await _make_user()
    try:
        async with _client() as client:
            created = await client.post(
                "/api/v1/claim-check/evaluate",
                json={"claim_text": "This savings account is guaranteed and risk-free"},
                headers=auth_headers(owner),
            )
            assert created.status_code == 201
            body = created.json()
            assert body["evidence_status"] == "unavailable"
            assert body["caution_score"] is None
            assert body["claim_type"] == "safety_guarantee"
            assert body["personal"]["monthly_budget_krw"] is not None
            evaluation_id = body["id"]

            history = await client.get("/api/v1/claim-check/history", headers=auth_headers(owner))
            assert [h["id"] for h in history.json()] == [evaluation_id]
            assert (await client.get("/api/v1/claim-check/history", headers=auth_headers(other))).json() == []
            assert (await client.get(f"/api/v1/claim-check/{evaluation_id}", headers=auth_headers(other))).status_code == 404
            fetched = await client.get(f"/api/v1/claim-check/{evaluation_id}", headers=auth_headers(owner))
            assert fetched.json()["factors"] == body["factors"]  # frozen, not recomputed

            assert (await client.delete(f"/api/v1/claim-check/{evaluation_id}", headers=auth_headers(other))).status_code == 404
            assert (await client.delete(f"/api/v1/claim-check/{evaluation_id}", headers=auth_headers(owner))).status_code == 204
    finally:
        await _cleanup(owner, other)


@pytest.mark.asyncio
async def test_live_search_is_cached_and_the_daily_budget_is_enforced(monkeypatch):
    if not await _db_reachable():
        pytest.skip("database not reachable")
    calls = []

    async def fake_search(query, country):
        calls.append(query)
        return [
            SearchHit(1, "Best savings", "https://www.nerdwallet.com/best?tag=x", f"{query} - the best savings account", "Sep 1, 2026"),
            SearchHit(2, "Warning", "https://www.reuters.com/x", f"{query} can be misleading, regulators warn", "Sep 2, 2026"),
        ]

    monkeypatch.setattr(claim_search, "search_sources", fake_search)
    monkeypatch.setattr(claim_check_service, "LIVE_SEARCHES_PER_USER_PER_DAY", 1)
    unique = uuid.uuid4().hex[:8]
    first_claim = f"Bank{unique} has the best savings account"
    second_claim = f"Card{unique} has the best cashback"
    user_id = await _make_user()
    hashes = tuple(
        claim_check_service._query_hash("us", claim_check_service.parse_claim(c).normalized_query)
        for c in (first_claim, second_claim)
    )
    try:
        async with _client() as client:
            first = await client.post("/api/v1/claim-check/evaluate", json={"claim_text": first_claim, "country": "us"}, headers=auth_headers(user_id))
            again = await client.post("/api/v1/claim-check/evaluate", json={"claim_text": first_claim, "country": "us"}, headers=auth_headers(user_id))
            third = await client.post("/api/v1/claim-check/evaluate", json={"claim_text": second_claim, "country": "us"}, headers=auth_headers(user_id))

        assert first.json()["evidence_status"] == "live"
        assert first.json()["source_count"] == 2
        assert first.json()["caution_score"] is not None
        assert again.json()["evidence_status"] == "cached"
        assert third.json()["evidence_status"] == "quota_exhausted"
        assert len(calls) == 1  # the cache and the budget both prevented further searches
    finally:
        await _cleanup(user_id, query_hashes=hashes)


@pytest.mark.asyncio
async def test_unsupported_stake_currency_is_rejected():
    if not await _db_reachable():
        pytest.skip("database not reachable")
    user_id = await _make_user()
    try:
        async with _client() as client:
            response = await client.post(
                "/api/v1/claim-check/evaluate",
                json={"claim_text": "This stock will double next year", "stake_amount": 100, "stake_currency": "XYZ"},
                headers=auth_headers(user_id),
            )
        assert response.status_code == 422
    finally:
        await _cleanup(user_id)
