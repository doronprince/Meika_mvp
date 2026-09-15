"""Pure tests for the survival engine — no database, no network. Every
expected runway here is worked out by hand in the comment above it."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import ExpenseCategory
from app.schemas.common import RiskLevel
from app.schemas.survival import (
    CurrencyDevaluationShock,
    ExpenseIncreaseShock,
    IncomeLossShock,
    InflationShock,
    OneOffExpenseShock,
    SurvivalSimulationRequest,
    SurvivalState,
)
from app.services.currency_display import DisplayCurrency
from app.services.survival_service import (
    EngineInputs,
    IncomeLine,
    build_presets,
    build_report,
    shapley_attribution,
    simulate,
)

KRW = DisplayCurrency("KRW", Decimal("1"))
HOUSING = ExpenseCategory.HOUSING_AND_UTILITIES
DINING = ExpenseCategory.CAFES_AND_DINING


def make_inputs(savings, *, income=0.0, essential=0.0, discretionary=0.0, currency="KRW", horizon=60):
    incomes = (IncomeLine(stream_id=None, label="Job", currency=currency, monthly_krw=income),) if income else ()
    categories = {}
    if essential:
        categories[HOUSING] = essential
    if discretionary:
        categories[DINING] = discretionary
    return EngineInputs(savings_krw=savings, incomes=incomes, category_monthly_krw=categories, horizon_months=horizon)


def test_constant_burn_runway_is_savings_over_net_outflow():
    # 1,000,000 at 250,000/month hits exactly zero at the end of month 4.
    assert simulate(make_inputs(1_000_000, essential=250_000), []).runway_months == pytest.approx(4.0)
    # At 300,000/month: 100,000 left after month 3 covers 1/3 of month 4.
    assert simulate(make_inputs(1_000_000, essential=300_000), []).runway_months == pytest.approx(10 / 3)


def test_income_covering_spend_is_sustainable():
    assert simulate(make_inputs(100_000, income=500_000, essential=300_000), []).runway_months is None


def test_one_off_expense_lands_in_its_month():
    # Month 1: 1,000,000 - 250,000 - 500,000 = 250,000; month 2 reaches exactly 0.
    run = simulate(make_inputs(1_000_000, essential=250_000), [OneOffExpenseShock(amount_krw=Decimal("500000"), month=1)])
    assert run.balances[0] == pytest.approx(250_000)
    assert run.runway_months == pytest.approx(2.0)


def test_income_loss_shortens_runway():
    # Net outflow 100,000 -> 6 months; halving income doubles it -> 3 months.
    inputs = make_inputs(600_000, income=200_000, essential=300_000)
    assert simulate(inputs, []).runway_months == pytest.approx(6.0)
    assert simulate(inputs, [IncomeLossShock(pct=Decimal("50"))]).runway_months == pytest.approx(3.0)


def test_temporary_income_loss_ends_after_its_duration():
    # Two months with no income cost 600,000, then income matches spend again.
    inputs = make_inputs(1_000_000, income=300_000, essential=300_000, horizon=24)
    run = simulate(inputs, [IncomeLossShock(pct=Decimal("100"), duration_months=2)])
    assert run.balances[1] == pytest.approx(400_000)
    assert run.balances[-1] == pytest.approx(400_000)
    assert run.runway_months is None


def test_devaluation_only_hits_income_paid_in_that_currency():
    shock = CurrencyDevaluationShock(currency="inr", pct=Decimal("25"))
    krw = make_inputs(1_000_000, income=200_000, essential=300_000, currency="KRW")
    inr = make_inputs(1_000_000, income=200_000, essential=300_000, currency="INR")
    assert simulate(krw, [shock]).runway_months == simulate(krw, []).runway_months
    # INR income now buys 150,000 KRW, so the net outflow is 150,000.
    assert simulate(inr, [shock]).runway_months == pytest.approx(1_000_000 / 150_000)


def test_expense_increase_targets_named_category_or_all_essentials():
    inputs = make_inputs(1_200_000, essential=200_000, discretionary=100_000)
    # Dining doubles: 200,000 + 200,000 = 400,000/month -> 3 months.
    assert simulate(inputs, [ExpenseIncreaseShock(pct=Decimal("100"), category=DINING)]).runway_months == pytest.approx(3.0)
    # No category = essentials only: 300,000 + 100,000 = 400,000/month -> 3 months.
    assert simulate(inputs, [ExpenseIncreaseShock(pct=Decimal("50"))]).runway_months == pytest.approx(3.0)


def test_inflation_compounds_monthly_on_essentials_only():
    inputs = make_inputs(10_000_000, essential=100_000, discretionary=50_000, horizon=12)
    run = simulate(inputs, [InflationShock(annual_pct=Decimal("12"))])
    expected_spend = sum(100_000 * 1.12 ** (month / 12) for month in range(1, 13)) + 50_000 * 12
    assert 10_000_000 - run.balances[-1] == pytest.approx(expected_spend)


def test_discretionary_cuts_trigger_below_buffer_and_extend_runway():
    # Without cuts: 900,000 at 300,000/month -> 3.0 months.
    # With cuts (trigger 600,000): month 3 starts at 300,000 < 600,000, so dining
    # halves: month 3 spends 250,000 -> 50,000 left, which covers 50/250 of month 4.
    inputs = make_inputs(900_000, essential=200_000, discretionary=100_000)
    cuts = simulate(inputs, [], cut_pct=50, cut_trigger_krw=600_000)
    assert simulate(inputs, []).runway_months == pytest.approx(3.0)
    assert cuts.cuts_start_month == 3
    assert cuts.runway_months == pytest.approx(3.2)


SHOCKS = [
    IncomeLossShock(pct=Decimal("40")),
    ExpenseIncreaseShock(pct=Decimal("20")),
    CurrencyDevaluationShock(currency="USD", pct=Decimal("30"), start_month=3),
    OneOffExpenseShock(amount_krw=Decimal("400000"), month=2),
]


def test_shapley_values_sum_exactly_to_joint_loss():
    inputs = make_inputs(3_000_000, income=400_000, essential=550_000, discretionary=150_000, currency="USD")
    shapley, standalone, joint = shapley_attribution(inputs, SHOCKS)
    assert joint > 0
    assert sum(shapley) == pytest.approx(joint, abs=1e-9)
    assert len(standalone) == len(SHOCKS)


def test_identical_shocks_receive_identical_credit():
    inputs = make_inputs(2_000_000, income=300_000, essential=400_000)
    shapley, _, _ = shapley_attribution(inputs, [IncomeLossShock(pct=Decimal("20")), IncomeLossShock(pct=Decimal("20"))])
    assert shapley[0] == pytest.approx(shapley[1])


def test_overlapping_shocks_report_negative_interaction():
    # Baseline 20 months. Losing all income: 5 months (-15). Devaluing that
    # income 50%: 8 months (-12). Both: still 5 months (-15), not -27, because
    # the devaluation has nothing left to destroy.
    inputs = make_inputs(2_000_000, income=300_000, essential=400_000, currency="USD")
    shocks = [IncomeLossShock(pct=Decimal("100")), CurrencyDevaluationShock(currency="USD", pct=Decimal("50"))]
    _, standalone, joint = shapley_attribution(inputs, shocks)
    assert standalone == [pytest.approx(15.0), pytest.approx(12.0)]
    assert joint == pytest.approx(15.0)


def test_individually_survivable_shocks_can_compound():
    # Surplus of 100,000/month. Income -15% leaves +25,000; costs +15% leave
    # +40,000; together -35,000/month, so savings run out at 28.6 months.
    inputs = make_inputs(1_000_000, income=500_000, essential=400_000, horizon=60)
    shocks = [IncomeLossShock(pct=Decimal("15")), ExpenseIncreaseShock(pct=Decimal("15"))]
    _, standalone, joint = shapley_attribution(inputs, shocks)
    assert standalone == [pytest.approx(0.0), pytest.approx(0.0)]
    assert joint == pytest.approx(60 - 1_000_000 / 35_000)


def test_report_without_savings_invents_no_runway():
    report = build_report(
        savings_krw=None,
        incomes=[],
        category_monthly_krw={HOUSING: 300_000.0},
        spend_source="ledger",
        ledger_days=40,
        monthly_budget_krw=Decimal("600000"),
        request=SurvivalSimulationRequest(),
        display=KRW,
        today=date(2026, 9, 15),
    )
    assert report.state == SurvivalState.NEEDS_SAVINGS
    assert report.baseline_runway is None
    assert report.trajectory == []
    assert report.baseline.monthly_essential_krw == Decimal("300000.00")
    assert any(f.label == "Liquid savings not set" for f in report.factors)


def test_report_attribution_is_consistent_and_explained():
    report = build_report(
        savings_krw=Decimal("3000000"),
        incomes=[IncomeLine(None, "Allowance", "USD", 400_000.0)],
        category_monthly_krw={HOUSING: 550_000.0, DINING: 150_000.0},
        spend_source="ledger",
        ledger_days=90,
        monthly_budget_krw=Decimal("600000"),
        request=SurvivalSimulationRequest(shocks=SHOCKS, horizon_months=60),
        display=KRW,
        today=date(2026, 9, 15),
    )
    assert report.state == SurvivalState.COMPUTED
    assert len(report.attributions) == len(SHOCKS)
    assert abs(report.attribution_residual_months) < 1e-6
    assert sum(a.months_lost for a in report.attributions) == pytest.approx(report.joint_months_lost, abs=0.05)
    assert report.shocked_runway.months < report.baseline_runway.months
    assert report.shocked_with_cuts_runway.months >= report.shocked_runway.months
    assert report.risk_level == RiskLevel.MODERATE
    assert len(report.trajectory) == 60
    labels = {f.label for f in report.factors}
    assert {"Starting balance", "Baseline runway", "Runway under all selected shocks", "Attribution adds up"} <= labels


def test_presets_follow_the_users_own_data():
    job_id = uuid.uuid4()
    incomes = [
        IncomeLine(job_id, "Part-time job", "KRW", 800_000.0),
        IncomeLine(uuid.uuid4(), "Family allowance", "INR", 300_000.0),
    ]
    by_key = {p.key: p for p in build_presets(incomes, {HOUSING: 400_000.0, DINING: 100_000.0}, KRW)}
    assert by_key["lose_largest_income"].shock.income_stream_id == job_id
    assert "devalue_inr_20" in by_key
    assert "housing_up_10" in by_key
    assert by_key["emergency_one_month_essentials"].shock.amount_krw == Decimal("400000.00")


def test_presets_without_income_skip_income_shocks():
    keys = {p.key for p in build_presets([], {None: 600_000.0}, KRW)}
    assert "lose_largest_income" not in keys
    assert "essentials_up_10" in keys
