import uuid

import pytest

from app.core.config import settings
from app.core.rate_limit import reset_rate_limits
from app.core.security import create_access_token


def auth_headers(user_id: uuid.UUID | str) -> dict[str, str]:
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture(autouse=True)
def _disable_live_price_search(monkeypatch):
    """SerpApi's free tier is 100 searches/month -- the test suite must
    never spend it. Every price-finder test that passes a `q` would
    otherwise hit the real live API on each run. Tests that specifically
    want to exercise the live path re-enable it with monkeypatch directly."""
    monkeypatch.setattr(settings, "serpapi_api_key", "")


@pytest.fixture(autouse=True)
def _fresh_rate_limit_buckets():
    """Each test starts with empty rate-limit windows, so the suite's pass/fail
    never depends on test order or how many requests earlier tests made.
    The limiter's own test still trips it deliberately within one test."""
    reset_rate_limits()
    yield
