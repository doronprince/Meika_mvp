import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.fx_service import FRANKFURTER_BASE_URL


async def _fx_api_reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{FRANKFURTER_BASE_URL}/latest", params={"from": "KRW"})
            return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.asyncio
async def test_fx_rates_for_krw_includes_major_currencies():
    if not await _fx_api_reachable():
        pytest.skip("live FX API not reachable")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/fx/rates", params={"base": "KRW"})

    assert response.status_code == 200
    body = response.json()
    assert body["base"] == "KRW"
    assert "USD" in body["rates"]
    assert "EUR" in body["rates"]
    assert float(body["rates"]["USD"]) > 0


@pytest.mark.asyncio
async def test_fx_rates_rejects_unsupported_currency():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/fx/rates", params={"base": "XXX"})

    assert response.status_code == 422
