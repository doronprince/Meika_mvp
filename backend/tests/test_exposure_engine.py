"""Pure tests for the exposure-vs-spending statistics — no database."""

import random
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.enums import ExposureKind
from app.schemas.exposure import AssociationVerdict, InsightState
from app.services.currency_display import DisplayCurrency
from app.services.exposure_service import (
    MIN_SHIFT_DAYS,
    Session,
    Spend,
    _ranks,
    association,
    compute_insights,
)

KRW = DisplayCurrency("KRW", Decimal("1"))
AS_OF = date(2026, 9, 18)


def days_back(n: int) -> list[date]:
    return [AS_OF - timedelta(days=n - 1 - i) for i in range(n)]


def test_ranks_average_ties():
    assert _ranks([10, 20, 20, 5]) == [2.0, 3.5, 3.5, 1.0]


def test_identical_series_have_rho_one_and_the_smallest_possible_p():
    days = days_back(40)
    x = [float(i % 5 + (i * 7) % 11) for i in range(40)]
    result = association(x, days, x, days, demean=False)
    assert result.spearman_rho == pytest.approx(1.0)
    shifts = 40 - 2 * MIN_SHIFT_DAYS + 1
    assert result.n_permutations == shifts
    assert result.p_value == pytest.approx(1 / (1 + shifts), abs=1e-4)


def test_weekday_demeaning_removes_a_shared_weekend_rhythm():
    # Exposure and spending are both higher on weekends and otherwise
    # unrelated noise. The raw correlation looks strong; once each series'
    # weekday means are removed it disappears. (The raw p-value is not
    # tiny: rotations by whole weeks keep weekends aligned, so the
    # permutation null already absorbs part of the rhythm. The misleading
    # part is the correlation a reader would see.)
    rng = random.Random(3)
    days = days_back(84)
    weekend = [1.0 if d.weekday() >= 5 else 0.0 for d in days]
    exposure = [60 * w + rng.uniform(0, 20) for w in weekend]
    spend = [30_000 * w + rng.uniform(0, 10_000) for w in weekend]
    raw = association(exposure, days, spend, days, demean=False)
    demeaned = association(exposure, days, spend, days, demean=True)
    assert raw.spearman_rho > 0.5
    assert abs(demeaned.spearman_rho) < 0.3
    assert demeaned.p_value > 0.05


def _sessions_and_spend(effect: bool, seed: int = 11, n_days: int = 70):
    rng = random.Random(seed)
    sessions, spends = [], []
    for day in days_back(n_days):
        minutes = rng.choice([0, 0, 0, 20, 45, 90, 120]) if day != AS_OF else 120
        if minutes:
            sessions.append(Session(day, minutes, ExposureKind.SHOPPING_APP, "Coupang"))
        base = rng.uniform(0, 8_000)
        spends.append(Spend(day, base, True))
        if effect and minutes >= 90:
            spends.append(Spend(day + timedelta(days=1), 40_000 + rng.uniform(0, 5_000), True))
        spends.append(Spend(day, 15_000, False))  # essential spend never counts
    return sessions, [s for s in spends if s.occurred_on <= AS_OF]


def test_injected_next_day_effect_is_detected_and_triggers_a_nudge():
    sessions, spends = _sessions_and_spend(effect=True)
    report = compute_insights(sessions, spends, as_of=AS_OF, display=KRW)
    assert report.state == InsightState.COMPUTED
    assert report.verdict == AssociationVerdict.ASSOCIATION
    assert report.primary.p_value < 0.05
    assert report.effect is not None and report.effect.difference_krw > 0
    assert report.intervention.triggered
    assert report.intervention.top_platform == "Coupang"
    assert any(f.label == "Screen time lines up with your spending" for f in report.factors)


def test_no_effect_means_no_association_and_no_nudge():
    sessions, spends = _sessions_and_spend(effect=False)
    report = compute_insights(sessions, spends, as_of=AS_OF, display=KRW)
    assert report.state == InsightState.COMPUTED
    assert report.verdict == AssociationVerdict.NO_CLEAR_ASSOCIATION
    assert not report.intervention.triggered


def test_short_tracking_period_reports_insufficient_data():
    sessions = [Session(d, 30, ExposureKind.SOCIAL_FEED, "Instagram") for d in days_back(10)]
    report = compute_insights(sessions, [], as_of=AS_OF, display=KRW)
    assert report.state == InsightState.INSUFFICIENT_DATA
    assert report.primary is None and report.verdict is None
    assert not report.intervention.triggered
    assert any(f.label == "Not enough data yet" for f in report.factors)


def test_nothing_after_as_of_is_read():
    sessions, spends = _sessions_and_spend(effect=True)
    earlier = AS_OF - timedelta(days=5)
    later_only = [s for s in sessions if s.occurred_on <= earlier], [s for s in spends if s.occurred_on <= earlier]
    a = compute_insights(sessions, spends, as_of=earlier, display=KRW)
    b = compute_insights(*later_only, as_of=earlier, display=KRW)
    assert a.primary == b.primary
    assert a.effect == b.effect
