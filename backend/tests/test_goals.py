import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.enums import ExpenseCategory, GoalType
from app.models.user import User
from app.schemas.goal import GoalVerdict
from app.services.currency_display import DisplayCurrency
from app.services.dashboard_service import MIN_DAYS_FOR_PROJECTION
from app.services.goal_forecast import AT_RISK_MAX_PACE_CHANGE, forecast_goal
from tests.conftest import auth_headers

KRW = DisplayCurrency("KRW", Decimal("1"))
START = date(2026, 9, 1)
END = date(2026, 9, 30)  # 30-day window


def _forecast(goal_type=GoalType.SAVINGS, *, target="300000", progress, today, starting="0", category=None):
    return forecast_goal(
        goal_type=goal_type,
        target_krw=Decimal(target),
        start_date=START,
        target_date=END,
        today=today,
        progress_krw=Decimal(progress),
        display=KRW,
        starting_krw=Decimal(starting),
        category=category,
    )


# --- pure forecast: no database needed -------------------------------------


def test_savings_on_pace_is_on_track_with_margin_counterfactual():
    # Day 10 of 30, 10,000/day -> projects exactly 300,000.
    f = _forecast(progress="100000", today=date(2026, 9, 10))

    assert f.verdict == GoalVerdict.ON_TRACK
    assert f.days_elapsed == 10 and f.days_remaining == 20 and f.days_total == 30
    assert f.pace_krw_per_day == Decimal("10000.00")
    assert f.projected_final_krw == Decimal("300000.00")
    assert f.required_krw_per_day == Decimal("10000.00")
    assert f.required_change_krw_per_day == Decimal("0.00")
    assert [x.label for x in f.factors][-1] == "Margin"


def test_savings_counterfactual_is_recomputable_by_hand():
    # Day 10, 8,000/day. Needs (300,000 - 80,000) / 20 = 11,000/day: +3,000 = 37.5% of pace.
    f = _forecast(progress="80000", today=date(2026, 9, 10))

    assert f.required_krw_per_day == Decimal("11000.00")
    assert f.required_change_krw_per_day == Decimal("3000.00")
    assert f.projected_final_krw == Decimal("240000.00")
    # 37.5% > the 25% band -> off track, and the factor says why.
    assert f.verdict == GoalVerdict.OFF_TRACK
    fix = f.factors[-1]
    assert fix.label == "What would fix it"
    assert fix.value == 3000.0
    assert "38% of your current pace" in fix.detail


def test_savings_small_gap_is_at_risk():
    # Day 10, 9,000/day. Needs 210,000 / 20 = 10,500/day: +1,500 = 16.7% of pace.
    f = _forecast(progress="90000", today=date(2026, 9, 10))

    assert f.required_change_krw_per_day / f.pace_krw_per_day <= AT_RISK_MAX_PACE_CHANGE
    assert f.verdict == GoalVerdict.AT_RISK


def test_savings_zero_pace_is_off_track_not_at_risk():
    f = _forecast(progress="0", today=date(2026, 9, 10))

    assert f.pace_krw_per_day == Decimal("0.00")
    assert f.verdict == GoalVerdict.OFF_TRACK


def test_opening_balance_counts_toward_progress_but_not_pace():
    # 100,000 set aside up front + 50,000 contributed over 10 days = 5,000/day, not 15,000/day.
    f = _forecast(progress="150000", starting="100000", today=date(2026, 9, 10))

    assert f.progress_percent == Decimal("50.00")
    assert f.pace_krw_per_day == Decimal("5000.00")
    assert f.projected_final_krw == Decimal("250000.00")


def test_early_days_withhold_projection_but_still_give_required_rate():
    today = START + timedelta(days=MIN_DAYS_FOR_PROJECTION - 2)
    f = _forecast(progress="1000", today=today)

    assert f.verdict == GoalVerdict.INSUFFICIENT_DATA
    assert f.projected_final_krw is None
    # Required rate is plain arithmetic, not a projection -> still available.
    assert f.required_krw_per_day is not None
    assert any(x.label == "Projection not yet available" for x in f.factors)


def test_not_started_goal_is_insufficient_data():
    f = _forecast(progress="0", today=START - timedelta(days=3))

    assert f.verdict == GoalVerdict.INSUFFICIENT_DATA
    assert f.days_elapsed == 0 and f.days_remaining == 30


def test_savings_reached_early_is_achieved():
    assert _forecast(progress="300000", today=date(2026, 9, 12)).verdict == GoalVerdict.ACHIEVED


def test_savings_short_after_deadline_is_missed():
    f = _forecast(progress="250000", today=date(2026, 10, 3))

    assert f.verdict == GoalVerdict.MISSED
    assert f.days_remaining == 0 and f.days_elapsed == 30
    assert f.factors[-1].value == 50000.0


def test_cap_under_pace_is_on_track_with_headroom():
    # 100,000 cap; 2,000/day over 10 days projects 60,000.
    f = _forecast(GoalType.SPENDING_CAP, target="100000", progress="20000", today=date(2026, 9, 10),
                  category=ExpenseCategory.CAFES_AND_DINING)

    assert f.verdict == GoalVerdict.ON_TRACK
    assert f.required_krw_per_day == Decimal("4000.00")  # (100,000 - 20,000) / 20
    assert f.required_change_krw_per_day == Decimal("-2000.00")
    assert f.factors[-1].label == "Headroom"
    assert "Cafes And Dining spending" in f.factors[0].detail


def test_cap_slightly_over_pace_is_at_risk_and_says_what_to_cut():
    # 100,000 cap; 3,500/day over 10 days projects 105,000. Allowed 65,000/20 = 3,250/day: cut 250 (7%).
    f = _forecast(GoalType.SPENDING_CAP, target="100000", progress="35000", today=date(2026, 9, 10))

    assert f.projected_final_krw == Decimal("105000.00")
    assert f.required_change_krw_per_day == Decimal("250.00")
    assert f.verdict == GoalVerdict.AT_RISK
    assert "cut ₩250/day" in f.factors[-1].detail


def test_cap_far_over_pace_is_off_track():
    # 6,000/day projects 180,000 on a 100,000 cap. Allowed 2,000/day: cut 4,000 (67%).
    f = _forecast(GoalType.SPENDING_CAP, target="100000", progress="60000", today=date(2026, 9, 10))

    assert f.verdict == GoalVerdict.OFF_TRACK


def test_cap_already_exceeded_is_missed_immediately():
    f = _forecast(GoalType.SPENDING_CAP, target="100000", progress="100001", today=date(2026, 9, 10))

    assert f.verdict == GoalVerdict.MISSED
    assert f.required_krw_per_day is None


def test_cap_within_limit_after_deadline_is_achieved():
    f = _forecast(GoalType.SPENDING_CAP, target="100000", progress="90000", today=date(2026, 10, 1))

    assert f.verdict == GoalVerdict.ACHIEVED


def test_every_verdict_ships_with_factors():
    cases = [
        _forecast(progress="100000", today=date(2026, 9, 10)),
        _forecast(progress="0", today=START - timedelta(days=1)),
        _forecast(progress="300000", today=date(2026, 9, 5)),
        _forecast(GoalType.SPENDING_CAP, target="100000", progress="200000", today=date(2026, 9, 5)),
    ]
    for f in cases:
        assert f.factors, f.verdict
        assert all(x.detail for x in f.factors)


# --- API validation: rejected before any database access -------------------


def _goal_payload(**overrides):
    payload = {
        "name": "Winter trip",
        "goal_type": "savings",
        "target_amount_krw": "500000",
        "target_date": (date.today() + timedelta(days=60)).isoformat(),
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_goals_require_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/goals")

    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"target_amount_krw": "0"},
        {"target_date": (date.today() - timedelta(days=1)).isoformat()},
        {"category": "groceries"},  # category only applies to spending caps
        {"goal_type": "spending_cap", "starting_amount_krw": "1000"},
        {"goal_type": "not_a_goal_type"},
    ],
)
async def test_create_goal_rejects_inconsistent_payloads(overrides):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/goals", json=_goal_payload(**overrides), headers=auth_headers(uuid.uuid4()))

    assert response.status_code == 422


# --- end to end against a real database ------------------------------------


async def _db_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_goal_round_trip_with_contributions_expenses_and_tenant_isolation():
    if not await _db_reachable():
        pytest.skip("database not reachable")

    async with AsyncSessionLocal() as session:
        user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="test-hash")
        session.add(user)
        await session.commit()
        user_id = user.id

    headers = auth_headers(user_id)
    start = (date.today() - timedelta(days=9)).isoformat()
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/goals", json=_goal_payload(start_date=start, starting_amount_krw="50000"), headers=headers
            )
            assert created.status_code == 201, created.text
            goal = created.json()
            assert goal["forecast"]["progress_krw"] in ("50000.00", 50000.0)
            goal_id = goal["id"]

            contributed = await client.post(
                f"/api/v1/goals/{goal_id}/contributions", json={"amount_krw": "30000", "contributed_on": start},
                headers=headers,
            )
            assert contributed.status_code == 201, contributed.text
            forecast = contributed.json()["forecast"]
            assert float(forecast["progress_krw"]) == 80000.0
            assert forecast["days_elapsed"] == 10
            assert float(forecast["pace_krw_per_day"]) == 3000.0  # the opening 50,000 is excluded
            assert forecast["verdict"] in {"on_track", "at_risk", "off_track"}
            assert forecast["factors"]

            listed = await client.get(f"/api/v1/goals/{goal_id}/contributions", headers=headers)
            assert listed.status_code == 200 and len(listed.json()) == 1

            before_start = await client.post(
                f"/api/v1/goals/{goal_id}/contributions",
                json={"amount_krw": "1000", "contributed_on": (date.today() - timedelta(days=30)).isoformat()},
                headers=headers,
            )
            assert before_start.status_code == 422

            # A spending cap tracks real expenses, including transit, within its category.
            cap = await client.post(
                "/api/v1/goals",
                json=_goal_payload(name="Coffee cap", goal_type="spending_cap", target_amount_krw="50000",
                                   category="cafes_and_dining", start_date=start),
                headers=headers,
            )
            assert cap.status_code == 201, cap.text
            cap_id = cap.json()["id"]
            for category, amount in (("cafes_and_dining", "6000"), ("groceries", "40000")):
                expense = await client.post(
                    "/api/v1/expenses",
                    json={"title": "x", "category": category, "amount_krw": amount, "transit_cost_krw": "500",
                          "occurred_on": date.today().isoformat()},
                    headers=headers,
                )
                assert expense.status_code == 201
            cap_now = await client.get(f"/api/v1/goals/{cap_id}", headers=headers)
            assert float(cap_now.json()["forecast"]["progress_krw"]) == 6500.0

            no_contributions = await client.post(
                f"/api/v1/goals/{cap_id}/contributions", json={"amount_krw": "1000"}, headers=headers
            )
            assert no_contributions.status_code == 422

            stranger = auth_headers(uuid.uuid4())
            assert (await client.get(f"/api/v1/goals/{goal_id}", headers=stranger)).status_code == 404
            assert (await client.delete(f"/api/v1/goals/{goal_id}", headers=stranger)).status_code == 404
            assert (await client.get("/api/v1/goals", headers=stranger)).json() == []

            all_goals = await client.get("/api/v1/goals", headers=headers)
            assert {g["id"] for g in all_goals.json()} == {goal_id, cap_id}

            assert (await client.delete(f"/api/v1/goals/{goal_id}", headers=headers)).status_code == 204
            assert (await client.get(f"/api/v1/goals/{goal_id}", headers=headers)).status_code == 404
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            await session.commit()
