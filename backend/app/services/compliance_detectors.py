"""Pure arithmetic for tax & compliance foresight: no database, no I/O, no prose.

Every function takes plain values and returns plain values, so any number
can be recomputed by hand. Money is Decimal throughout — `statistics.stdev`
and `math.sqrt` are deliberately not used on amounts because both return
floats; `_stdev` below uses Decimal.sqrt(). `statistics.median` appears only
on integer day gaps.

Detection is split in two so the evaluation harness can sweep the band
constants cheaply: `measure_*` does the expensive work (matching, summing,
variance) once per ledger and day; `classify_*` turns a measurement into a
severity under a given BandConfig.
"""

import calendar
import re
import statistics
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from app.models.enums import ExpenseCategory
from app.schemas.common import RiskLevel
from app.schemas.compliance import SuppressionReason
from app.services.compliance_rules import ComplianceRuleSpec, ThresholdBasis, compiled_regex

# A tax-year projection multiplies a daily rate by up to 365, so it needs a
# full monthly cycle of history: at 30 days a monthly rent or tuition
# instalment is counted exactly once rather than zero or twice. (The
# dashboard's 7-day warm-up only extrapolates across one month.)
MIN_LEDGER_DAYS_FOR_PROJECTION = 30
# The speculative watch band leans on the fast edge of a rate interval,
# which needs a variance estimate from at least 3 complete months — which
# can't exist below ~90 days.
MIN_LEDGER_DAYS_FOR_WATCH_BAND = 90
MIN_COMPLETE_MONTHS_FOR_SIGMA = 3
# On the last day of a tax year the days remaining is 0 and every watch
# window would collapse, hiding exactly the spending about to roll into the
# next year. Looking at least 30 days ahead keeps the question alive.
MIN_HORIZON_DAYS = 30
# The longest window any shipped rule declares (365) plus slack, so a
# rolling year is never truncated by a month-end off-by-one.
MAX_LOOKBACK_DAYS = 400
DAYS_PER_MONTH = Decimal("30.4167")
MIN_RATE_PER_DAY = Decimal("0.01")

_CENTS = Decimal("0.01")
_RATIO = Decimal("0.0001")

SEVERITY_RANK = {RiskLevel.LOW: 0, RiskLevel.MODERATE: 1, RiskLevel.HIGH: 2}


def _q2(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class BandConfig:
    """The three constants that decide when a projection becomes a flag.
    Set from the sweep in scripts/eval_compliance_foresight.py, not by hand."""

    # LOW ("watch") fires when the fast edge of the rate range crosses the
    # assumed figure within this many horizons.
    watch_horizon_multiplier: Decimal
    # Before 30 days of history (no projection allowed), LOW fires once the
    # observed amount reaches this share of the assumed figure.
    early_ledger_low_ratio: Decimal
    # With fewer than 3 complete months, the rate range is rate x (1 ± this).
    # An admitted placeholder, disclosed verbatim in the explanation.
    fallback_rate_band: Decimal


# Set by scripts/eval_compliance_foresight.py (seed 20260910, 100 synthetic
# ledgers), using a selection rule fixed before the results were seen: take
# the most permissive value whose false-alarm rate stays at or under 10%, or
# the most conservative one if none does. No watch multiplier met the bar
# (LOW-or-above false alarms were 15.6% with the band off and 32-43% with it
# on), so the watch band ships switched off. The early-ledger flag didn't
# meet it either, so it ships at 1.0: nothing short of the figure itself.
# MODERATE projections alone measured 9.7% false alarms and 91.6% claim
# precision. 25% was the narrowest fallback band meeting the bar on MODERATE
# flags (15% gave 12.4%). The code paths stay, so a later sweep on real
# ledgers can switch them back on.
DEFAULT_BANDS = BandConfig(
    watch_horizon_multiplier=Decimal("0"),
    early_ledger_low_ratio=Decimal("1.0"),
    fallback_rate_band=Decimal("0.25"),
)


def cap_severity(severity: RiskLevel, max_severity: RiskLevel) -> RiskLevel:
    return severity if SEVERITY_RANK[severity] <= SEVERITY_RANK[max_severity] else max_severity


@dataclass(frozen=True)
class LedgerLine:
    """One logged expense, decoupled from the ORM so the evaluation harness
    can build ledgers without a database."""

    occurred_on: date
    title: str
    category: ExpenseCategory
    amount_krw: Decimal
    transit_cost_krw: Decimal = Decimal("0")
    store_name: str | None = None
    notes: str | None = None
    original_currency: str | None = None
    original_amount: Decimal | None = None
    has_documentation: bool = False
    expense_id: uuid.UUID | None = None

    @property
    def sort_key(self) -> tuple:
        return (self.occurred_on, str(self.expense_id or ""), self.title)

    @property
    def is_foreign(self) -> bool:
        return self.original_currency not in (None, "KRW")


@dataclass(frozen=True)
class FiscalWindow:
    start: date
    end: date
    is_default: bool


def fiscal_window(today: date, start_month: int = 1, start_day: int = 1, *, is_default: bool = True) -> FiscalWindow:
    def anchor(year: int) -> date:
        return date(year, start_month, min(start_day, calendar.monthrange(year, start_month)[1]))

    start = anchor(today.year) if today >= anchor(today.year) else anchor(today.year - 1)
    end = anchor(start.year + 1) - timedelta(days=1)
    return FiscalWindow(start=start, end=end, is_default=is_default)


@dataclass(frozen=True)
class EvalContext:
    today: date
    fiscal: FiscalWindow
    ledger_first_day: date | None

    @property
    def ledger_days(self) -> int:
        return (self.today - self.ledger_first_day).days + 1 if self.ledger_first_day else 0

    @property
    def days_remaining_fy(self) -> int:
        return (self.fiscal.end - self.today).days

    @property
    def horizon_days(self) -> int:
        return max(self.days_remaining_fy, MIN_HORIZON_DAYS)

    @property
    def projection_allowed(self) -> bool:
        return self.ledger_days >= MIN_LEDGER_DAYS_FOR_PROJECTION

    @property
    def watch_band_allowed(self) -> bool:
        return self.ledger_days >= MIN_LEDGER_DAYS_FOR_WATCH_BAND


def basis_amount(line: LedgerLine, amount_basis: str) -> Decimal:
    # Compliance defaults to the amount alone: the subway fare to the bank is
    # not part of the transfer. Each rule declares its basis explicitly.
    if amount_basis == "amount_plus_transit":
        return line.amount_krw + line.transit_cost_krw
    return line.amount_krw


def match_line(line: LedgerLine, rule: ComplianceRuleSpec, documentation_filter: str = "any") -> bool:
    m = rule.match
    if m.categories is not None and line.category not in m.categories:
        return False
    if m.min_amount_krw is not None and basis_amount(line, rule.amount_basis) < m.min_amount_krw:
        return False
    if m.currency_mode == "foreign_only" and not line.is_foreign:
        return False
    if m.currency_mode == "krw_only" and line.is_foreign:
        return False
    if m.text_regex:
        haystack = f"{line.title} {line.store_name or ''} {line.notes or ''}"
        if not compiled_regex(m.text_regex).search(haystack):
            return False
    if documentation_filter == "undocumented_only" and line.has_documentation:
        return False
    if documentation_filter == "documented_only" and not line.has_documentation:
        return False
    return True


def stdev(values: list[Decimal]) -> Decimal | None:
    """Sample standard deviation in Decimal (n - 1 denominator)."""
    n = len(values)
    if n < 2:
        return None
    mean = sum(values, Decimal("0")) / Decimal(n)
    squares = sum(((v - mean) ** 2 for v in values), Decimal("0"))
    return (squares / Decimal(n - 1)).sqrt()


def median_decimal(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)


def ceil_days(amount: Decimal, rate: Decimal) -> int:
    return int((amount / rate).to_integral_value(rounding=ROUND_CEILING))


def complete_months(span_start: date, today: date) -> list[tuple[int, int]]:
    """Calendar months lying entirely inside [span_start, the day before this
    month began]. The current month is always partial and is excluded: a
    partial month drags the mean down and inflates the variance."""
    year, month = span_start.year, span_start.month
    if span_start.day != 1:
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    months = []
    while (year, month) < (today.year, today.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


# --- Detector A: an amount accumulating toward an assumed figure ---------


@dataclass(frozen=True)
class AccumulationMeasure:
    window_start: date
    matched: tuple[LedgerLine, ...]
    observed_krw: Decimal
    other_window_total_krw: Decimal
    # observed / threshold / rate / sigma are in comparison units: KRW, or the
    # threshold's own currency when every matched line was logged in it.
    observed: Decimal
    threshold: Decimal
    exact_currency: str | None
    converted_count: int
    days_observed: int
    rate: Decimal
    sigma_month: Decimal | None
    sigma_months_used: int
    crossed_on: date | None
    crossing_line: LedgerLine | None
    crossing_cumulative: Decimal | None

    @property
    def exposure_ratio(self) -> Decimal:
        return (self.observed / self.threshold).quantize(_RATIO, rounding=ROUND_HALF_UP)


def measure_accumulation(
    rule: ComplianceRuleSpec,
    lines: list[LedgerLine],
    ctx: EvalContext,
    threshold_krw: Decimal,
    basis: ThresholdBasis | None,
) -> AccumulationMeasure | None:
    """None when nothing matches. `basis` is the threshold's original
    currency, passed only while the user hasn't overridden the figure."""
    params = rule.params
    window_days = int(params.get("window_days", 365))
    documentation_filter = params.get("documentation_filter", "any")
    rolling_start = ctx.today - timedelta(days=window_days - 1)
    if params.get("window_mode", "rolling_days") == "fiscal_ytd":
        window_start, other_start = ctx.fiscal.start, rolling_start
    else:
        window_start, other_start = rolling_start, ctx.fiscal.start

    candidates = [line for line in lines if line.occurred_on <= ctx.today and match_line(line, rule, documentation_filter)]
    matched = sorted((line for line in candidates if line.occurred_on >= window_start), key=lambda line: line.sort_key)
    if not matched:
        return None

    observed_krw = sum((basis_amount(line, rule.amount_basis) for line in matched), Decimal("0"))
    other_total = sum(
        (basis_amount(line, rule.amount_basis) for line in candidates if line.occurred_on >= other_start), Decimal("0")
    )

    exact = basis is not None and all(
        line.original_currency == basis.currency and line.original_amount is not None for line in matched
    )
    if exact:
        def amount(line: LedgerLine) -> Decimal:
            return line.original_amount
        threshold = basis.amount
        exact_currency = basis.currency
    else:
        def amount(line: LedgerLine) -> Decimal:
            return basis_amount(line, rule.amount_basis)
        threshold = threshold_krw
        exact_currency = None
    converted_count = sum(1 for line in matched if basis and line.original_currency != basis.currency)

    observed = sum((amount(line) for line in matched), Decimal("0"))
    span_start = max(window_start, ctx.ledger_first_day or window_start)
    days_observed = (ctx.today - span_start).days + 1
    rate = observed / Decimal(days_observed)

    months = complete_months(span_start, ctx.today)
    totals = {key: Decimal("0") for key in months}
    for line in matched:
        key = (line.occurred_on.year, line.occurred_on.month)
        if key in totals:
            totals[key] += amount(line)
    sigma_month = stdev(list(totals.values())) if len(months) >= MIN_COMPLETE_MONTHS_FOR_SIGMA else None

    crossed_on = crossing_line = crossing_cumulative = None
    running = Decimal("0")
    for line in matched:
        running += amount(line)
        if running >= threshold:
            crossed_on, crossing_line, crossing_cumulative = line.occurred_on, line, running
            break

    return AccumulationMeasure(
        window_start=window_start,
        matched=tuple(matched),
        observed_krw=observed_krw,
        other_window_total_krw=other_total,
        observed=observed,
        threshold=threshold,
        exact_currency=exact_currency,
        converted_count=converted_count,
        days_observed=days_observed,
        rate=rate,
        sigma_month=sigma_month,
        sigma_months_used=len(months) if sigma_month is not None else 0,
        crossed_on=crossed_on,
        crossing_line=crossing_line,
        crossing_cumulative=crossing_cumulative,
    )


@dataclass(frozen=True)
class Classification:
    severity: RiskLevel | None
    # How the severity was reached: "crossed", "projection", "watch",
    # "early_ratio" — or None when suppressed.
    path: str | None
    suppress_reason: SuppressionReason | None
    rate_hi: Decimal | None = None
    rate_lo: Decimal | None = None
    sigma_source: str | None = None
    days_to_cross_earliest: int | None = None
    days_to_cross_latest: int | None = None


def classify_accumulation(
    m: AccumulationMeasure, ctx: EvalContext, bands: BandConfig, max_severity: RiskLevel
) -> Classification:
    if m.observed >= m.threshold:
        return Classification(cap_severity(RiskLevel.HIGH, max_severity), "crossed", None)

    if not ctx.projection_allowed:
        # No projection below 30 days of history — only what is visible now.
        if m.observed >= bands.early_ledger_low_ratio * m.threshold:
            return Classification(cap_severity(RiskLevel.LOW, max_severity), "early_ratio", None)
        return Classification(None, None, SuppressionReason.INSUFFICIENT_HISTORY)

    if m.sigma_month is not None:
        sigma_daily = m.sigma_month / DAYS_PER_MONTH
        rate_hi = m.rate + sigma_daily
        rate_lo = max(MIN_RATE_PER_DAY, m.rate - sigma_daily)
        sigma_source = "matched_months"
    else:
        rate_hi = m.rate * (1 + bands.fallback_rate_band)
        rate_lo = m.rate * (1 - bands.fallback_rate_band)
        sigma_source = "fixed_fallback_band"

    remaining = m.threshold - m.observed
    earliest = ceil_days(remaining, rate_hi) if rate_hi > 0 else None
    latest = ceil_days(remaining, rate_lo) if rate_lo > MIN_RATE_PER_DAY else None
    numbers = dict(
        rate_hi=rate_hi,
        rate_lo=rate_lo,
        sigma_source=sigma_source,
        days_to_cross_earliest=earliest,
        days_to_cross_latest=latest,
    )

    if latest is not None and latest <= ctx.horizon_days:
        # Even the slow edge of the range crosses before the window closes.
        return Classification(cap_severity(RiskLevel.MODERATE, max_severity), "projection", None, **numbers)
    if (
        ctx.watch_band_allowed
        and earliest is not None
        and earliest <= bands.watch_horizon_multiplier * ctx.horizon_days
    ):
        # Only the fast edge crosses, or it crosses beyond the tax year but
        # within the watch window.
        return Classification(cap_severity(RiskLevel.LOW, max_severity), "watch", None, **numbers)
    return Classification(None, None, SuppressionReason.BELOW_EMISSION_BAND, **numbers)


# --- Detector B: one transaction against an assumed figure --------------


@dataclass(frozen=True)
class SingleLineMeasure:
    matched: tuple[LedgerLine, ...]
    largest: LedgerLine
    largest_amount: Decimal
    spread: Decimal
    threshold: Decimal

    @property
    def exposure_ratio(self) -> Decimal:
        return (self.largest_amount / self.threshold).quantize(_RATIO, rounding=ROUND_HALF_UP)


def measure_single_line(
    rule: ComplianceRuleSpec, lines: list[LedgerLine], ctx: EvalContext, threshold_krw: Decimal
) -> SingleLineMeasure | None:
    window_start = ctx.today - timedelta(days=int(rule.params.get("window_days", 365)) - 1)
    matched = sorted(
        (line for line in lines if window_start <= line.occurred_on <= ctx.today and match_line(line, rule)),
        key=lambda line: line.sort_key,
    )
    if not matched:
        return None
    amounts = [basis_amount(line, rule.amount_basis) for line in matched]
    largest_amount = max(amounts)
    largest = next(line for line, a in zip(matched, amounts) if a == largest_amount)
    return SingleLineMeasure(
        matched=tuple(matched),
        largest=largest,
        largest_amount=largest_amount,
        spread=stdev(amounts) or Decimal("0"),
        threshold=threshold_krw,
    )


def classify_single_line(m: SingleLineMeasure, ctx: EvalContext, max_severity: RiskLevel) -> Classification:
    # No middle band: a single transaction either reached the figure or it
    # didn't; there is no rate to project. The spread-based watch band obeys
    # the same 90-day gate as every other watch flag — a spread from a few
    # weeks of transfers is as thin as any other short-history estimate.
    if m.largest_amount >= m.threshold:
        return Classification(cap_severity(RiskLevel.HIGH, max_severity), "crossed", None)
    if ctx.watch_band_allowed and len(m.matched) >= 2 and m.largest_amount + m.spread >= m.threshold:
        return Classification(cap_severity(RiskLevel.LOW, max_severity), "watch", None)
    return Classification(None, None, SuppressionReason.BELOW_EMISSION_BAND)


# --- Detector C: a pattern of spending in several currencies ------------


@dataclass(frozen=True)
class FootprintMeasure:
    foreign: tuple[LedgerLine, ...]
    currencies: tuple[str, ...]
    foreign_total_krw: Decimal
    total_krw: Decimal
    share: Decimal
    months_spanned: int
    sustained_months: int
    conditions_met: int
    min_distinct: int
    min_share: Decimal
    min_months: int


def measure_currency_footprint(rule: ComplianceRuleSpec, lines: list[LedgerLine], ctx: EvalContext) -> FootprintMeasure | None:
    params = rule.params
    window_start = ctx.today - timedelta(days=int(params.get("window_days", 365)) - 1)
    in_window = [line for line in lines if window_start <= line.occurred_on <= ctx.today and match_line(line, rule)]
    foreign = sorted((line for line in in_window if line.is_foreign), key=lambda line: line.sort_key)
    if not foreign:
        return None

    min_distinct = int(params.get("min_distinct_currencies", 2))
    min_share = Decimal(str(params.get("min_foreign_share", "0.25")))
    min_months = int(params.get("min_months_spanned", 3))

    total = sum((basis_amount(line, rule.amount_basis) for line in in_window), Decimal("0"))
    foreign_total = sum((basis_amount(line, rule.amount_basis) for line in foreign), Decimal("0"))
    share = (foreign_total / total).quantize(_RATIO, rounding=ROUND_HALF_UP) if total > 0 else Decimal("0")

    by_month_total: dict[tuple[int, int], Decimal] = {}
    by_month_foreign: dict[tuple[int, int], Decimal] = {}
    for line in in_window:
        key = (line.occurred_on.year, line.occurred_on.month)
        value = basis_amount(line, rule.amount_basis)
        by_month_total[key] = by_month_total.get(key, Decimal("0")) + value
        if line.is_foreign:
            by_month_foreign[key] = by_month_foreign.get(key, Decimal("0")) + value
    sustained = sum(
        1 for key, value in by_month_foreign.items() if by_month_total[key] > 0 and value / by_month_total[key] >= min_share
    )
    currencies = tuple(sorted({line.original_currency for line in foreign}))
    conditions = [len(currencies) >= min_distinct, share >= min_share, len(by_month_foreign) >= min_months]

    return FootprintMeasure(
        foreign=tuple(foreign),
        currencies=currencies,
        foreign_total_krw=foreign_total,
        total_krw=total,
        share=share,
        months_spanned=len(by_month_foreign),
        sustained_months=sustained,
        conditions_met=sum(conditions),
        min_distinct=min_distinct,
        min_share=min_share,
        min_months=min_months,
    )


def classify_currency_footprint(m: FootprintMeasure, max_severity: RiskLevel) -> Classification:
    if m.conditions_met == 3 and m.sustained_months >= m.min_months:
        return Classification(cap_severity(RiskLevel.MODERATE, max_severity), "pattern", None)
    if m.conditions_met >= 2:
        return Classification(cap_severity(RiskLevel.LOW, max_severity), "pattern", None)
    return Classification(None, None, SuppressionReason.BELOW_EMISSION_BAND)


# --- Detector D: regular payments that run past the tax year end ---------


@dataclass(frozen=True)
class RecurringGroup:
    label: str
    category: ExpenseCategory
    lines: tuple[LedgerLine, ...]
    median_gap: int
    median_amount: Decimal
    variability: Decimal
    amount_in_current_fy: Decimal
    spills_into_next_fy: Decimal
    next_after_fy_end: date
    annualized: Decimal


def _group_key(line: LedgerLine) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", " ", (line.store_name or line.title).lower()).strip()


def measure_recurring(rule: ComplianceRuleSpec, lines: list[LedgerLine], ctx: EvalContext) -> list[RecurringGroup]:
    """Exact normalized-name grouping only — no fuzzy matching — so every
    group can be reproduced by hand from the evidence list."""
    params = rule.params
    min_occurrences = int(params.get("min_occurrences", 3))
    tolerance = int(params.get("interval_tolerance_days", 5))
    fy = ctx.fiscal

    groups: dict[tuple[str, str], list[LedgerLine]] = {}
    for line in lines:
        if line.occurred_on <= ctx.today and match_line(line, rule):
            groups.setdefault((line.category.value, _group_key(line)), []).append(line)

    qualifying: list[RecurringGroup] = []
    for (_, label), members in sorted(groups.items()):
        if len(members) < min_occurrences or not label:
            continue
        members.sort(key=lambda line: line.sort_key)
        dates = [line.occurred_on for line in members]
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        median_gap = int(statistics.median(gaps))
        if not 7 <= median_gap <= 372 or any(abs(g - median_gap) > tolerance for g in gaps):
            continue
        # A commitment that has stopped isn't going to cross anything.
        if (ctx.today - dates[-1]).days > median_gap + tolerance:
            continue
        if dates[-1] < fy.start:
            continue

        amounts = [basis_amount(line, rule.amount_basis) for line in members]
        median_amount = median_decimal(amounts)
        projected = []
        step = dates[-1] + timedelta(days=median_gap)
        while step <= fy.end + timedelta(days=median_gap):
            projected.append(step)
            step += timedelta(days=median_gap)
        after_end = [d for d in projected if d > fy.end]
        if not after_end:
            continue
        in_fy_actual = sum((a for line, a in zip(members, amounts) if fy.start <= line.occurred_on <= ctx.today), Decimal("0"))
        in_fy_projected = median_amount * Decimal(sum(1 for d in projected if ctx.today < d <= fy.end))
        qualifying.append(
            RecurringGroup(
                label=members[-1].store_name or members[-1].title,
                category=members[-1].category,
                lines=tuple(members),
                median_gap=median_gap,
                median_amount=median_amount,
                variability=((max(amounts) - min(amounts)) / median_amount).quantize(_RATIO) if median_amount else Decimal("0"),
                amount_in_current_fy=_q2(in_fy_actual + in_fy_projected),
                spills_into_next_fy=_q2(median_amount),
                next_after_fy_end=after_end[0],
                annualized=_q2(median_amount * Decimal(365) / Decimal(median_gap)),
            )
        )
    qualifying.sort(key=lambda g: (-g.annualized, g.label))
    return qualifying


def classify_recurring(groups: list[RecurringGroup], min_annual_krw: Decimal, max_severity: RiskLevel) -> Classification:
    if not groups:
        return Classification(None, None, SuppressionReason.NO_MATCHING_TRANSACTIONS)
    severity = RiskLevel.MODERATE if groups[0].annualized >= min_annual_krw else RiskLevel.LOW
    return Classification(cap_severity(severity, max_severity), "pattern", None)
