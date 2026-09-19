"""Pure-function tests for tax & compliance foresight — no database, no skip
guards. Expected values are written as literals worked out by hand, so a
reviewer can check them with a calculator."""

import dataclasses
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.models.enums import AssumptionSource, ExpenseCategory
from app.schemas.common import RiskLevel
from app.schemas.compliance import SuppressionReason
from app.services import compliance_detectors as det
from app.services.compliance_engine import REFERRAL_LABEL, evaluate_ledger
from app.services.compliance_rules import load_ruleset, parse_ruleset
from app.services.currency_display import DisplayCurrency

KRW = DisplayCurrency("KRW", Decimal("1"))
RULES = load_ruleset()
EDU = ExpenseCategory.EDUCATION


def _line(day: date, amount: str, category=ExpenseCategory.GROCERIES, title="Shop", **kw) -> det.LedgerLine:
    return det.LedgerLine(occurred_on=day, title=title, category=category, amount_krw=Decimal(amount), **kw)


def _ctx(today: date, first_day: date | None, month: int = 1, day: int = 1) -> det.EvalContext:
    return det.EvalContext(today=today, fiscal=det.fiscal_window(today, month, day), ledger_first_day=first_day)


# The gate tests below exercise the watch band and the early-ledger flag,
# which ship switched off (see DEFAULT_BANDS); they run with both on.
BANDS_ON = det.BandConfig(Decimal("2"), Decimal("0.5"), Decimal("0.25"))


def _evaluate(lines, today, *, overrides=None, first_day=None, ruleset=RULES, bands=det.DEFAULT_BANDS):
    first = first_day or min((line.occurred_on for line in lines), default=None)
    return evaluate_ledger(
        lines=lines,
        ctx=_ctx(today, first),
        ruleset=ruleset,
        overrides=overrides or {},
        display=KRW,
        expense_count=len(lines),
        bands=bands,
    )


# --- arithmetic ---------------------------------------------------------


def test_threshold_accumulation_matches_hand_computed_values():
    today = date(2026, 6, 15)
    lines = [_line(date(2026, 1, 1), "10000")] + [
        _line(date(2026, month, 10), amount, EDU, "Tuition")
        for month, amount in ((1, "600000"), (2, "600000"), (3, "600000"), (4, "900000"), (5, "600000"), (6, "300000"))
    ]
    rule = RULES.get("education_spend_fiscal_year")
    ctx = _ctx(today, date(2026, 1, 1))

    m = det.measure_accumulation(rule, lines, ctx, Decimal("5000000"), None)

    assert m.observed == Decimal("3600000")
    assert m.days_observed == 166  # 1 Jan .. 15 Jun inclusive
    # Monthly totals Jan-May: 600k x4 and 900k; mean 660k; sample variance
    # (4 x 60k^2 + 240k^2) / 4 = 1.8e10; sqrt = 134,164.08.
    assert m.sigma_months_used == 5
    assert m.sigma_month.quantize(Decimal("0.01")) == Decimal("134164.08")

    c = det.classify_accumulation(m, ctx, det.DEFAULT_BANDS, rule.max_severity)
    # rate 3.6M/166 = 21,686.75/day; sigma/day = 134,164.08/30.4167 = 4,410.87.
    # 1.4M remaining / 26,097.62 = 53.6 -> 54 days; / 17,275.88 = 81.0 -> 82 days.
    assert (c.days_to_cross_earliest, c.days_to_cross_latest) == (54, 82)
    assert c.sigma_source == "matched_months"
    # 82 days < the 199 left in the tax year: even the slow edge crosses.
    assert c.severity == RiskLevel.MODERATE and c.path == "projection"


def test_crossing_is_found_by_an_explicit_running_total():
    today = date(2026, 6, 15)
    lines = [_line(date(2026, 1, 1), "10000")] + [
        _line(date(2026, month, 10), "2000000", EDU, f"Tuition {month}") for month in (2, 3, 4)
    ]
    rule = RULES.get("education_spend_fiscal_year")
    m = det.measure_accumulation(rule, lines, _ctx(today, date(2026, 1, 1)), Decimal("5000000"), None)

    assert m.crossed_on == date(2026, 4, 10)
    assert m.crossing_line.title == "Tuition 4"
    assert m.crossing_cumulative == Decimal("6000000")


def test_money_never_becomes_float():
    today = date(2026, 6, 15)
    lines = [_line(date(2026, 1, 1), "10000")] + [
        _line(date(2026, month, 10), "700000", EDU, "Tuition") for month in range(1, 7)
    ]
    rule = RULES.get("education_spend_fiscal_year")
    m = det.measure_accumulation(rule, lines, _ctx(today, date(2026, 1, 1)), Decimal("5000000"), None)
    for field in dataclasses.fields(m):
        assert not isinstance(getattr(m, field.name), float), field.name


# --- history gates ------------------------------------------------------


def test_projection_is_withheld_below_thirty_days_of_history():
    today = date(2026, 6, 15)
    first = today - timedelta(days=11)  # 12 days of history
    over_half = [_line(first, "10000"), _line(today, "3000000", EDU, "Tuition")]
    result = _evaluate(over_half, today, bands=BANDS_ON)

    flag = next(f for f in result.flags if f.rule_key == "education_spend_fiscal_year")
    assert flag.severity == RiskLevel.LOW
    assert flag.cross_earliest_on is None and flag.cross_latest_on is None
    unavailable = next(f for f in flag.factors if f.label == "Projection not yet available")
    assert unavailable.value is None

    under_half = [_line(first, "10000"), _line(today, "1000000", EDU, "Tuition")]
    suppressed = next(
        s for s in _evaluate(under_half, today, bands=BANDS_ON).suppressed if s.rule_key == "education_spend_fiscal_year"
    )
    assert suppressed.reason == SuppressionReason.INSUFFICIENT_HISTORY
    assert (suppressed.days_observed, suppressed.days_required) == (12, 30)


def test_watch_band_needs_ninety_days_of_history():
    # 1 Nov: 60 days left in the tax year. One ₩2.5M tuition payment against
    # ₩5M, so remaining / rate == days of history (89 or 91). With fewer than
    # 3 complete months the range is rate x 1.25 / x 0.75: earliest ~72 days
    # (within 2 x 60), latest ~119 (beyond 60) — only the watch band can fire.
    today = date(2026, 11, 1)
    outcomes = {}
    for history in (89, 91):
        lines = [_line(today - timedelta(days=history - 1), "10000"), _line(today - timedelta(days=1), "2500000", EDU)]
        result = _evaluate(lines, today, bands=BANDS_ON)
        flag = next((f for f in result.flags if f.rule_key == "education_spend_fiscal_year"), None)
        suppressed = next((s for s in result.suppressed if s.rule_key == "education_spend_fiscal_year"), None)
        outcomes[history] = flag.severity if flag else suppressed.reason

    assert outcomes[89] == SuppressionReason.BELOW_EMISSION_BAND
    assert outcomes[91] == RiskLevel.LOW


def test_shipped_bands_keep_the_watch_band_and_early_flag_off():
    # The same 91-day ledger that the watch band flags when switched on is
    # left alone with the shipped (measured) constants...
    today = date(2026, 11, 1)
    lines = [_line(today - timedelta(days=90), "10000"), _line(today - timedelta(days=1), "2500000", EDU)]
    suppressed = next(s for s in _evaluate(lines, today).suppressed if s.rule_key == "education_spend_fiscal_year")
    assert suppressed.reason == SuppressionReason.BELOW_EMISSION_BAND
    # ...and so is a young ledger over half the figure.
    young = [_line(today - timedelta(days=11), "10000"), _line(today, "3000000", EDU)]
    early = next(s for s in _evaluate(young, today).suppressed if s.rule_key == "education_spend_fiscal_year")
    assert early.reason == SuppressionReason.INSUFFICIENT_HISTORY


# --- detectors ----------------------------------------------------------


def test_exact_currency_path_uses_no_exchange_rate():
    today = date(2026, 6, 15)
    lines = [
        _line(date(2025, 7, 1) + timedelta(days=30 * i), "1350000", title="Wise transfer to mum",
              original_currency="USD", original_amount=Decimal("1000"))
        for i in range(11)
    ]
    result = _evaluate(lines, today)
    flag = next(f for f in result.flags if f.rule_key == "foreign_remittance_rolling_year")

    basis = next(f for f in flag.factors if f.label == "Currency basis")
    assert "exact" in basis.detail
    # 11 x USD 1,000 against USD 10,000.
    assert flag.severity == RiskLevel.HIGH
    assert flag.exposure_ratio == Decimal("1.1000")


def test_single_large_transfer_bands():
    today = date(2026, 6, 15)
    rule = RULES.get("large_single_transfer")

    def classify(*amounts, history_days=120):
        lines = [_line(today - timedelta(days=10 * i), a, title="Western Union") for i, a in enumerate(amounts)]
        ctx = _ctx(today, today - timedelta(days=history_days - 1))
        m = det.measure_single_line(rule, lines, ctx, Decimal("4050000"))
        return det.classify_single_line(m, ctx, rule.max_severity)

    assert classify("4100000").severity == RiskLevel.HIGH
    # 3.5M + spread 353,553 = 3.85M < 4.05M.
    assert classify("3000000", "3500000").suppress_reason == SuppressionReason.BELOW_EMISSION_BAND
    # 3.9M + spread 636,396 = 4.54M >= 4.05M.
    assert classify("3000000", "3900000").severity == RiskLevel.LOW
    # The same spread with under 90 days of history is too thin to watch on.
    assert classify("3000000", "3900000", history_days=60).severity is None
    # ...but a transfer that actually reached the figure is flagged at any age.
    assert classify("4100000", history_days=10).severity == RiskLevel.HIGH


def test_pattern_detectors_never_reach_high():
    today = date(2026, 9, 1)
    lines = []
    for i in range(12):
        month = date(2025, 10, 1) + timedelta(days=31 * i)
        lines.append(_line(month, "200000", title="Hotel", original_currency="JPY", original_amount=Decimal("22000")))
        lines.append(_line(month + timedelta(days=3), "200000", title="Train", original_currency="EUR", original_amount=Decimal("135")))
        lines.append(_line(month, "900000", ExpenseCategory.HOUSING_AND_UTILITIES, "Rent", store_name="Gangnam Studio"))
    result = _evaluate(lines, today)

    for key in ("foreign_currency_footprint", "fiscal_boundary_commitments"):
        flag = next(f for f in result.flags if f.rule_key == key)
        assert flag.severity == RiskLevel.MODERATE


def test_recurring_payment_spills_past_the_tax_year_end():
    today = date(2026, 11, 20)
    lines = [
        _line(date(2026, month, 5), "500000", ExpenseCategory.HOUSING_AND_UTILITIES, "Rent", store_name="Gangnam Studio")
        for month in range(6, 12)
    ]
    groups = det.measure_recurring(RULES.get("fiscal_boundary_commitments"), lines, _ctx(today, date(2026, 6, 5)))

    assert len(groups) == 1
    group = groups[0]
    assert group.median_gap == 31  # gaps 30/31 days, median 31 (sorted 30,30,31,31,31)
    # Projection steps by the median gap, not the calendar: 5 Nov + 31 days =
    # 6 Dec (inside the year), + 31 = 6 Jan 2027 (after it).
    assert group.next_after_fy_end == date(2027, 1, 6)
    assert group.annualized == Decimal("5887096.77")  # 500,000 x 365 / 31


def test_fiscal_window_handles_non_january_and_leap_day_starts():
    uk = det.fiscal_window(date(2026, 4, 5), 4, 6)
    assert (uk.start, uk.end) == (date(2025, 4, 6), date(2026, 4, 5))
    leap = det.fiscal_window(date(2027, 3, 1), 2, 29)
    assert leap.start == date(2027, 2, 28)


def test_shipped_regexes_are_not_catastrophic():
    adversarial = "remit" * 2000
    for rule in RULES.rules:
        if rule.match.text_regex:
            started = time.perf_counter()
            re.compile(rule.match.text_regex, re.IGNORECASE).search(adversarial + "!")
            assert time.perf_counter() - started < 0.05, rule.rule_key


# --- the assembled result ----------------------------------------------


def _mixed_ledger(today: date) -> list[det.LedgerLine]:
    start = today - timedelta(days=399)
    lines = []
    for i in range(13):
        day = start + timedelta(days=30 * i)
        lines.append(_line(day, "1150000", title="Remittance to family", store_name="Wise",
                           expense_id=uuid.UUID(int=i + 1)))
        lines.append(_line(day + timedelta(days=2), "450000", EDU, "Tuition instalment",
                           store_name="Yonsei KLI", expense_id=uuid.UUID(int=100 + i)))
        lines.append(_line(day + timedelta(days=4), "150000", title="Dinner", original_currency="USD",
                           original_amount=Decimal("110"), expense_id=uuid.UUID(int=200 + i)))
    return lines


FORBIDDEN_PATTERNS = [
    r"\byou must file\b", r"\bthe law requires\b", r"\byou owe\b", r"\bis taxable\b",
    r"\bis deductible\b", r"\byou are required to\b", r"\bthis is illegal\b",
    r"\bwe recommend (?:you )?(?:file|claim|declare)\b",
]


def test_every_rule_appears_exactly_once_and_every_flag_ends_with_referral():
    today = date(2026, 9, 19)
    result = _evaluate(_mixed_ledger(today), today)

    flagged = {f.rule_key for f in result.flags}
    suppressed = {s.rule_key for s in result.suppressed}
    assert flagged.isdisjoint(suppressed)
    assert flagged | suppressed == {r.rule_key for r in RULES.rules}
    assert result.counts.rules_evaluated == len(RULES.rules)
    for flag in result.flags:
        assert flag.factors[-1].label == REFERRAL_LABEL


def test_prose_never_asserts_law():
    today = date(2026, 9, 19)
    result = _evaluate(_mixed_ledger(today), today)
    texts = [result.disclaimer]
    for flag in result.flags:
        texts += [flag.title, flag.question] + [f"{x.label} {x.detail}" for x in flag.factors]
    texts += [s.detail for s in result.suppressed]
    joined = "\n".join(texts)
    for pattern in FORBIDDEN_PATTERNS:
        assert not re.search(pattern, joined, re.IGNORECASE), pattern


def test_engine_is_deterministic():
    today = date(2026, 9, 19)
    ledger = _mixed_ledger(today)
    first = _evaluate(ledger, today).model_dump_json()
    second = _evaluate(list(reversed(ledger)), today).model_dump_json()
    assert first == second


def _recompute_severity(flag, result, bands=det.DEFAULT_BANDS) -> RiskLevel | None:
    """Independent of the engine: rebuilds an accumulation flag's severity
    from the published fields alone."""
    ratio = flag.exposure_ratio
    horizon = max(result.fiscal_window.days_remaining, det.MIN_HORIZON_DAYS)
    ledger_days = result.coverage.ledger_days
    if ratio >= 1:
        return RiskLevel.HIGH
    if ledger_days < det.MIN_LEDGER_DAYS_FOR_PROJECTION:
        return RiskLevel.LOW if ratio >= bands.early_ledger_low_ratio else None
    if flag.cross_latest_on and (flag.cross_latest_on - result.as_of).days <= horizon:
        return RiskLevel.MODERATE
    if (
        ledger_days >= det.MIN_LEDGER_DAYS_FOR_WATCH_BAND
        and flag.cross_earliest_on
        and (flag.cross_earliest_on - result.as_of).days <= bands.watch_horizon_multiplier * horizon
    ):
        return RiskLevel.LOW
    return None


def test_explanation_is_sufficient_to_recompute_each_verdict():
    accumulation_keys = {r.rule_key for r in RULES.rules if r.detector_kind.value == "threshold_accumulation"}
    checked = 0
    for today in (date(2026, 2, 1), date(2026, 6, 15), date(2026, 9, 19), date(2026, 12, 20)):
        result = _evaluate(_mixed_ledger(today), today)
        for flag in result.flags:
            if flag.rule_key in accumulation_keys:
                assert _recompute_severity(flag, result) == flag.severity, (today, flag.rule_key)
                checked += 1
    assert checked > 0


def test_overrides_change_the_figure_and_can_disable_a_rule():
    today = date(2026, 9, 19)
    ledger = _mixed_ledger(today)
    own_figure = SimpleNamespace(
        threshold_amount_krw=Decimal("1000000"), is_enabled=True, assumption_source=AssumptionSource.USER_SET,
        verified_at=None, verified_note=None,
    )
    result = _evaluate(ledger, today, overrides={"education_spend_fiscal_year": own_figure})
    flag = next(f for f in result.flags if f.rule_key == "education_spend_fiscal_year")
    assert flag.severity == RiskLevel.HIGH
    assert flag.assumed_threshold_krw == Decimal("1000000")
    assert "You set this figure yourself." in " ".join(f.detail for f in flag.factors)

    verified = dataclasses.replace(
        det.LedgerLine(date(2026, 1, 1), "x", EDU, Decimal("1")),  # placeholder to prove replace works on lines
    )
    assert verified.amount_krw == Decimal("1")

    off = SimpleNamespace(threshold_amount_krw=None, is_enabled=False, assumption_source=AssumptionSource.UNVERIFIED_DEFAULT,
                          verified_at=None, verified_note=None)
    disabled = _evaluate(ledger, today, overrides={"foreign_remittance_rolling_year": off})
    suppressed = next(s for s in disabled.suppressed if s.rule_key == "foreign_remittance_rolling_year")
    assert suppressed.reason == SuppressionReason.RULE_DISABLED_BY_USER


def test_verified_figure_is_labelled_as_the_users_claim():
    today = date(2026, 9, 19)
    verified = SimpleNamespace(
        threshold_amount_krw=Decimal("1000000"), is_enabled=True, assumption_source=AssumptionSource.USER_VERIFIED,
        verified_at=datetime(2026, 9, 1, tzinfo=timezone.utc), verified_note="asked my accountant",
    )
    result = _evaluate(_mixed_ledger(today), today, overrides={"education_spend_fiscal_year": verified})
    flag = next(f for f in result.flags if f.rule_key == "education_spend_fiscal_year")
    assumption = next(f for f in flag.factors if f.label == "The figure Meika is assuming")
    assert "checked with a professional on Sep 1, 2026 (asked my accountant)" in assumption.detail


def test_empty_ledger_suppresses_every_rule_honestly():
    result = _evaluate([], date(2026, 9, 19))
    assert result.flags == []
    assert {s.reason for s in result.suppressed} == {SuppressionReason.NO_LEDGER}


def test_invalid_rule_is_reported_not_raised():
    raw = {
        "version": "test",
        "rules": [
            RULES.get("education_spend_fiscal_year").model_dump(mode="json"),
            {"rule_key": "broken", "title": "Broken rule", "detector_kind": "threshold_accumulation"},
        ],
    }
    ruleset = parse_ruleset(raw)
    today = date(2026, 9, 19)
    result = _evaluate(_mixed_ledger(today), today, ruleset=ruleset)

    broken = next(s for s in result.suppressed if s.rule_key == "broken")
    assert broken.reason == SuppressionReason.RULE_SPEC_INVALID
    assert any(f.rule_key == "education_spend_fiscal_year" for f in result.flags) or any(
        s.rule_key == "education_spend_fiscal_year" for s in result.suppressed
    )
