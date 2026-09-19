import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.ai import copilot_service
from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.enums import ExpenseCategory
from app.models.expense import Expense
from app.models.user import User
from app.services.compliance_engine import REFERRAL_LABEL
from app.services.compliance_rules import load_ruleset
from tests.conftest import auth_headers


async def _db_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1 FROM expense_tax_annotations LIMIT 1"))
        return True
    except Exception:
        return False


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_foresight_requires_auth():
    async with _client() as client:
        response = await client.get("/api/v1/compliance/foresight")
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method, path, body",
    [
        ("put", "/api/v1/compliance/settings", {"fiscal_year_start_month": 13}),
        ("put", "/api/v1/compliance/settings", {"residence_jurisdiction": "KOR"}),
        ("put", "/api/v1/compliance/rules/education_spend_fiscal_year/override", {"threshold_amount_krw": "0"}),
        ("put", "/api/v1/compliance/rules/education_spend_fiscal_year/override", {"is_enabled": None}),
    ],
)
async def test_invalid_payloads_are_rejected(method, path, body):
    async with _client() as client:
        response = await getattr(client, method)(path, json=body, headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unknown_rule_is_not_found():
    async with _client() as client:
        response = await client.put(
            "/api/v1/compliance/rules/not_a_rule/override", json={"is_enabled": False}, headers=auth_headers(uuid.uuid4())
        )
    assert response.status_code == 404


async def _make_user(expenses: list[tuple[date, str, ExpenseCategory, str]]) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.flush()
        for day, title, category, amount in expenses:
            session.add(Expense(user_id=user.id, title=title, category=category, amount_krw=Decimal(amount), occurred_on=day))
        await session.commit()
        return user.id


async def _delete_users(*user_ids: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        for user_id in user_ids:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await session.commit()


def _ledger() -> list[tuple[date, str, ExpenseCategory, str]]:
    today = date.today()
    rows = []
    for i in range(6):
        day = today - timedelta(days=30 * i + 1)
        rows.append((day, "Wise transfer home", ExpenseCategory.OTHER, "900000"))
        rows.append((day, "Tuition instalment", ExpenseCategory.EDUCATION, "400000"))
    return rows


@pytest.mark.asyncio
async def test_foresight_for_unknown_user_is_not_found():
    if not await _db_reachable():
        pytest.skip("database not reachable or compliance migration not applied")
    async with _client() as client:
        response = await client.get("/api/v1/compliance/foresight", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_foresight_overrides_settings_round_trip():
    if not await _db_reachable():
        pytest.skip("database not reachable or compliance migration not applied")
    user_id = await _make_user(_ledger())
    headers = auth_headers(user_id)
    try:
        async with _client() as client:
            response = await client.get("/api/v1/compliance/foresight", headers=headers)
            assert response.status_code == 200, response.text
            body = response.json()
            keys = {f["rule_key"] for f in body["flags"]} | {s["rule_key"] for s in body["suppressed"]}
            assert keys == {r.rule_key for r in load_ruleset().rules}
            assert "score" not in body
            for flag in body["flags"]:
                assert flag["factors"][-1]["label"] == REFERRAL_LABEL

            # Education so far is ₩2.4M against an assumed ₩5M. Lower the
            # figure to ₩1M and it has been reached.
            lowered = await client.put(
                "/api/v1/compliance/rules/education_spend_fiscal_year/override",
                json={"threshold_amount_krw": "1000000"},
                headers=headers,
            )
            assert lowered.status_code == 200
            assert lowered.json()["assumption_source"] == "user_set"
            after = (await client.get("/api/v1/compliance/foresight", headers=headers)).json()
            edu = next(f for f in after["flags"] if f["rule_key"] == "education_spend_fiscal_year")
            assert edu["severity"] == "high"

            verified = await client.put(
                "/api/v1/compliance/rules/education_spend_fiscal_year/override",
                json={"assumption_source": "user_verified", "verified_note": "checked with my accountant"},
                headers=headers,
            )
            assert verified.json()["verified_at"] is not None

            # The same ledger for a different user still sees the default figure.
            other = await _make_user(_ledger())
            try:
                other_body = (await client.get("/api/v1/compliance/foresight", headers=auth_headers(other))).json()
                other_edu = [f for f in other_body["flags"] if f["rule_key"] == "education_spend_fiscal_year"]
                assert all(f["severity"] != "high" for f in other_edu)
            finally:
                await _delete_users(other)

            reset = await client.delete("/api/v1/compliance/rules/education_spend_fiscal_year/override", headers=headers)
            assert reset.status_code == 204
            rules = (await client.get("/api/v1/compliance/rules", headers=headers)).json()
            edu_rule = next(r for r in rules if r["rule_key"] == "education_spend_fiscal_year")
            assert edu_rule["assumption_source"] == "unverified_default"
            assert float(edu_rule["effective_threshold_krw"]) == 5000000.0

            settings_before = (await client.get("/api/v1/compliance/settings", headers=headers)).json()
            assert settings_before["is_default"] is True
            updated = await client.put(
                "/api/v1/compliance/settings",
                json={"residence_jurisdiction": "au", "fiscal_year_start_month": 7},
                headers=headers,
            )
            assert updated.status_code == 200
            assert updated.json() == {
                "residence_jurisdiction": "AU",
                "home_jurisdiction": None,
                "fiscal_year_start_month": 7,
                "fiscal_year_start_day": 1,
                "is_default": False,
            }
            window = (await client.get("/api/v1/compliance/foresight", headers=headers)).json()["fiscal_window"]
            assert date.fromisoformat(window["start"]).month == 7
    finally:
        await _delete_users(user_id)


@pytest.mark.asyncio
async def test_annotating_another_users_expense_is_not_found():
    if not await _db_reachable():
        pytest.skip("database not reachable or compliance migration not applied")
    owner = await _make_user([(date.today(), "Tuition", ExpenseCategory.EDUCATION, "500000")])
    intruder = await _make_user([])
    try:
        async with AsyncSessionLocal() as session:
            expense_id = (await session.execute(text("SELECT id FROM expenses WHERE user_id = :u"), {"u": owner})).scalar()

        async with _client() as client:
            stolen = await client.post(
                "/api/v1/compliance/annotations",
                json={"expense_id": str(expense_id), "has_documentation": True},
                headers=auth_headers(intruder),
            )
            assert stolen.status_code == 404

            own = await client.post(
                "/api/v1/compliance/annotations",
                json={"expense_id": str(expense_id), "has_documentation": True, "document_ref": "uni email"},
                headers=auth_headers(owner),
            )
            assert own.status_code == 200
            assert own.json()["has_documentation"] is True

        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(text("SELECT user_id FROM expense_tax_annotations WHERE expense_id = :e"), {"e": expense_id})
            ).scalars().all()
        assert rows == [owner]
    finally:
        await _delete_users(owner, intruder)


class _ExplodingGenai:
    class Client:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Gemini must not be called for a tax question")


@pytest.mark.asyncio
async def test_tax_question_never_reaches_gemini_and_ends_with_referral(monkeypatch):
    if not await _db_reachable():
        pytest.skip("database not reachable or compliance migration not applied")
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(copilot_service, "genai", _ExplodingGenai)
    user_id = await _make_user(_ledger())
    try:
        async with AsyncSessionLocal() as session:
            reply, factors = await copilot_service.generate_reply(
                session, user_id, "Do I have to declare the money I remit home for tax?"
            )
        assert factors and factors[-1].label == REFERRAL_LABEL
        assert "not a statement about the law" in reply or "doesn't know the law" in reply
    finally:
        await _delete_users(user_id)


def test_tax_reply_answers_about_the_topic_asked():
    from types import SimpleNamespace

    flags = [
        SimpleNamespace(rule_key="undocumented_deduction_candidates"),
        SimpleNamespace(rule_key="foreign_remittance_rolling_year"),
    ]
    asked_about_transfers = copilot_service._pick_tax_flag(flags, "Do I need to declare the money I remit home?")
    assert asked_about_transfers.rule_key == "foreign_remittance_rolling_year"
    # No topic in the question: the most severe flag (first) answers.
    general = copilot_service._pick_tax_flag(flags, "Anything tax-wise I should know about?")
    assert general.rule_key == "undocumented_deduction_candidates"
