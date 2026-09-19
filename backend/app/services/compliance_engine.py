"""Turns detector arithmetic into explained flags. Pure and synchronous: no
database, no I/O, so the evaluation harness and the tests drive exactly the
code the API serves.

[[no-tax-advice]]: every flag is a POSSIBLE issue headed by a question, never
a finding. Its explanation always includes the assumed figure (named as an
assumption, with where it came from) and always ends with the
professional-referral factor, appended here in code so neither a rule author
nor a UI change can drop it. There is deliberately no aggregate score.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.models.enums import AssumptionSource
from app.schemas.common import RiskLevel, XAIFactor
from app.schemas.compliance import (
    ComplianceCounts,
    ComplianceDetectorKind,
    ComplianceFlag,
    ComplianceForesightResult,
    FiscalWindowRead,
    FlagEvidenceItem,
    LedgerCoverage,
    SuppressedRule,
    SuppressionReason,
)
from app.services import compliance_detectors as det
from app.services.compliance_rules import ComplianceRuleSpec, Ruleset
from app.services.currency_display import DisplayCurrency

DISCLAIMER = (
    "Meika is not a tax adviser and does not know the law anywhere. Everything below is arithmetic on the "
    "expenses you logged, compared against figures you can and should change. Treat each item as a question "
    "to bring to a qualified professional, never as an answer."
)

CANNOT_SEE = [
    "income or salary",
    "bank balances or where accounts are held",
    "investments or other assets",
    "transfers you didn't log",
    "the days you spent in any country",
]

REFERRAL_LABEL = "Confirm this with a qualified professional"
MAX_EVIDENCE = 25

_REQUIRED_DAYS = {
    ComplianceDetectorKind.CURRENCY_FOOTPRINT: det.MIN_LEDGER_DAYS_FOR_WATCH_BAND,
    ComplianceDetectorKind.RECURRING_BOUNDARY: det.MIN_LEDGER_DAYS_FOR_WATCH_BAND,
}


def _day(d: date) -> str:
    return f"{d:%b} {d.day}, {d.year}"


def _pct(ratio: Decimal) -> str:
    return f"{ratio * 100:.0f}%"


@dataclass(frozen=True)
class EffectiveRule:
    spec: ComplianceRuleSpec
    threshold_krw: Decimal | None
    # The threshold's original currency, kept only while the user hasn't
    # replaced the figure with their own KRW amount.
    use_basis: bool
    assumption_source: AssumptionSource
    is_enabled: bool
    verified_at: datetime | None
    verified_note: str | None


def effective_rule(spec: ComplianceRuleSpec, override: Any | None) -> EffectiveRule:
    """Merges the packaged rule with the user's override row (anything with
    threshold_amount_krw / is_enabled / assumption_source / verified_at /
    verified_note attributes). Nothing else about a rule is user-mutable."""
    packaged = spec.threshold.amount_krw if spec.threshold else None
    own = getattr(override, "threshold_amount_krw", None) if override is not None else None
    return EffectiveRule(
        spec=spec,
        threshold_krw=own if own is not None else packaged,
        use_basis=own is None,
        assumption_source=getattr(override, "assumption_source", None) or AssumptionSource.UNVERIFIED_DEFAULT,
        is_enabled=getattr(override, "is_enabled", True) if override is not None else True,
        verified_at=getattr(override, "verified_at", None) if override is not None else None,
        verified_note=getattr(override, "verified_note", None) if override is not None else None,
    )


def referral_factor(jurisdiction: str | None) -> XAIFactor:
    return XAIFactor(
        label=REFERRAL_LABEL,
        detail=(
            "This is a pattern Meika computed from your own logged spending. It is not a finding, not advice, and "
            f"not a statement about the law in {jurisdiction or 'your country'}. Only a licensed tax professional "
            "there can tell you whether it matters."
        ),
        value=None,
    )


def coverage_factor(coverage: LedgerCoverage, today: date) -> XAIFactor:
    if coverage.first_day is None:
        detail = "You haven't logged any expenses yet, so Meika has nothing to look at."
    else:
        detail = (
            f"Meika sees only the {coverage.expense_count} expense(s) you logged, from {_day(coverage.first_day)} to "
            f"{_day(today)}. It can't see {', '.join(CANNOT_SEE)}, which is what most real reporting rules depend on."
        )
    return XAIFactor(label="What Meika can see", detail=detail, value=float(coverage.expense_count))


def _assumption_factor(rule: EffectiveRule, display: DisplayCurrency) -> XAIFactor:
    spec = rule.spec
    basis_clause = f" ({spec.basis_note})" if rule.use_basis and spec.basis_note else ""
    if rule.assumption_source == AssumptionSource.USER_VERIFIED and rule.verified_at:
        note = f" ({rule.verified_note})" if rule.verified_note else ""
        provenance = f"You marked this figure as checked with a professional on {_day(rule.verified_at.date())}{note}."
    elif rule.assumption_source == AssumptionSource.USER_SET:
        provenance = "You set this figure yourself."
    else:
        provenance = "This is Meika's unverified default."
    return XAIFactor(
        label="The figure Meika is assuming",
        detail=(
            f"Meika is comparing this against an assumed figure of {display.format(rule.threshold_krw)}{basis_clause}. "
            f"{provenance} Meika doesn't know whether any such figure applies to you. {spec.verification_prompt}"
        ),
        value=float(rule.threshold_krw),
    )


def _evidence(lines: Sequence[det.LedgerLine]) -> list[FlagEvidenceItem]:
    newest_first = sorted(lines, key=lambda line: line.sort_key, reverse=True)[:MAX_EVIDENCE]
    return [
        FlagEvidenceItem(
            expense_id=line.expense_id,
            occurred_on=line.occurred_on,
            title=line.title,
            amount_krw=line.amount_krw,
            original_currency=line.original_currency,
            original_amount=line.original_amount,
            has_documentation=line.has_documentation,
        )
        for line in newest_first
    ]


# --- per-detector evaluation --------------------------------------------


@dataclass(frozen=True)
class RuleOutcome:
    flag: ComplianceFlag | None
    suppressed: SuppressedRule | None


def _suppress(spec: ComplianceRuleSpec, reason: SuppressionReason, detail: str, **days) -> RuleOutcome:
    return RuleOutcome(
        None, SuppressedRule(rule_key=spec.rule_key, title=spec.title, reason=reason, detail=detail, **days)
    )


def _flag(spec: ComplianceRuleSpec, severity: RiskLevel, factors: list[XAIFactor], jurisdiction: str | None, **fields) -> RuleOutcome:
    return RuleOutcome(
        ComplianceFlag(
            rule_key=spec.rule_key,
            title=spec.title,
            question=spec.question,
            severity=severity,
            factors=[*factors, referral_factor(jurisdiction)],
            **fields,
        ),
        None,
    )


def _evaluate_accumulation(
    rule: EffectiveRule,
    lines: Sequence[det.LedgerLine],
    ctx: det.EvalContext,
    display: DisplayCurrency,
    bands: det.BandConfig,
    coverage: LedgerCoverage,
    jurisdiction: str | None,
) -> RuleOutcome:
    spec = rule.spec
    basis = spec.threshold.basis if (rule.use_basis and spec.threshold) else None
    m = det.measure_accumulation(spec, list(lines), ctx, rule.threshold_krw, basis)
    if m is None:
        return _suppress(spec, SuppressionReason.NO_MATCHING_TRANSACTIONS, f"Meika found no {spec.match_description}.")
    c = det.classify_accumulation(m, ctx, bands, spec.max_severity)

    def fmt(amount: Decimal) -> str:
        return f"{m.exact_currency} {amount:,.2f}" if m.exact_currency else display.format(amount)

    if c.severity is None:
        if c.suppress_reason == SuppressionReason.INSUFFICIENT_HISTORY:
            return _suppress(
                spec,
                c.suppress_reason,
                f"Meika has {ctx.ledger_days} day(s) of logged history; projecting this rule needs "
                f"{det.MIN_LEDGER_DAYS_FOR_PROJECTION}. So far it matches {display.format(m.observed_krw)} against an "
                f"assumed {display.format(rule.threshold_krw)}.",
                days_observed=ctx.ledger_days,
                days_required=det.MIN_LEDGER_DAYS_FOR_PROJECTION,
            )
        return _suppress(
            spec,
            SuppressionReason.BELOW_EMISSION_BAND,
            f"Matched {fmt(m.observed)} against an assumed {fmt(m.threshold)} ({_pct(m.exposure_ratio)}). At the rate "
            "Meika has observed it wouldn't reach that figure within the window Meika watches.",
        )

    rolling = spec.params.get("window_mode", "rolling_days") != "fiscal_ytd"
    window_label = "the last 12 months" if rolling else f"this tax year (since {_day(ctx.fiscal.start)})"
    other_label = f"this tax year (since {_day(ctx.fiscal.start)})" if rolling else "the last 12 months"
    factors = [
        XAIFactor(
            label="What Meika found",
            detail=(
                f"Over {window_label} Meika found {len(m.matched)} matching transaction(s) totalling "
                f"{display.format(m.observed_krw)}. Over {other_label} the same rule matches "
                f"{display.format(m.other_window_total_krw)}. Both are shown because Meika can't know which period a "
                "real rule would use."
            ),
            value=float(m.observed_krw),
        ),
        _assumption_factor(rule, display),
    ]

    fields: dict[str, Any] = {}
    if c.path == "crossed":
        fields["crossed_on"] = m.crossed_on
        factors.append(
            XAIFactor(
                label="Assumed figure reached",
                detail=(
                    f"The running total reached the assumed figure on {_day(m.crossed_on)}, at "
                    f"'{m.crossing_line.title}', which took it to {fmt(m.crossing_cumulative)}."
                ),
                value=float(m.exposure_ratio * 100),
            )
        )
    elif not ctx.projection_allowed:
        factors.append(
            XAIFactor(
                label="Projection not yet available",
                detail=(
                    f"Meika has {ctx.ledger_days} day(s) of logged history; projecting ahead needs at least "
                    f"{det.MIN_LEDGER_DAYS_FOR_PROJECTION}. This is flagged only because the amount already seen is "
                    f"{_pct(m.exposure_ratio)} of the assumed figure (the cut-off is "
                    f"{_pct(bands.early_ledger_low_ratio)})."
                ),
                value=None,
            )
        )
    else:
        earliest, latest = c.days_to_cross_earliest, c.days_to_cross_latest
        fields["cross_earliest_on"] = ctx.today + timedelta(days=earliest)
        fields["cross_latest_on"] = ctx.today + timedelta(days=latest) if latest is not None else None
        when = (
            f"between {_day(fields['cross_earliest_on'])} and {_day(fields['cross_latest_on'])}, {earliest} to {latest} "
            "days from now"
            if latest is not None
            else f"on {_day(fields['cross_earliest_on'])} at the earliest ({earliest} days from now); at the slow "
            "edge of the range it doesn't get there"
        )
        floor_note = (
            f" Meika always looks at least {det.MIN_HORIZON_DAYS} days ahead, even at the very end of a tax year."
            if ctx.days_remaining_fy < det.MIN_HORIZON_DAYS
            else ""
        )
        watch_note = (
            f" Only the fast edge of the range gets there within {bands.watch_horizon_multiplier:g}x that "
            f"window ({int(bands.watch_horizon_multiplier * ctx.horizon_days)} days), so this is a 'watch'."
            if c.path == "watch"
            else ""
        )
        factors.append(
            XAIFactor(
                label="Where the current pace leads",
                detail=(
                    f"At the {fmt(m.rate)}/day rate Meika has observed, this would reach the assumed figure {when}. "
                    f"Your tax year ends {_day(ctx.fiscal.end)}, {ctx.days_remaining_fy} day(s) away.{floor_note}"
                    f"{watch_note}"
                ),
                value=float(earliest),
            )
        )
        if c.sigma_source == "matched_months":
            variability = (
                f"The date range comes from your own month-to-month variation for this rule: {fmt(m.sigma_month)} "
                f"across {m.sigma_months_used} complete months."
            )
            sigma_value = float(m.sigma_month / det.DAYS_PER_MONTH)
        else:
            variability = (
                f"Fewer than {det.MIN_COMPLETE_MONTHS_FOR_SIGMA} complete months of history exist for this rule, so "
                f"the range uses a fixed plus-or-minus {_pct(bands.fallback_rate_band)} band. That "
                f"{_pct(bands.fallback_rate_band)} is an arbitrary placeholder, not a measurement."
            )
            sigma_value = None
        factors.append(XAIFactor(label="How wide the range is, and why", detail=variability, value=sigma_value))

    if spec.threshold and spec.threshold.basis and rule.use_basis:
        currency = spec.threshold.basis.currency
        if m.exact_currency:
            detail = (
                f"All {len(m.matched)} matching transactions were entered in {currency}, so this comparison is exact: "
                "no exchange rate is involved."
            )
            value = None
        else:
            detail = (
                f"{m.converted_count} of {len(m.matched)} matching transactions were entered in a currency other than "
                f"{currency} and were converted to KRW at the rate on the day each was logged; the assumed figure is "
                f"held at a frozen rate. The comparison is therefore approximate."
            )
            value = float(m.converted_count)
        factors.append(XAIFactor(label="Currency basis", detail=detail, value=value))

    annotatable = spec.params.get("documentation_filter") == "undocumented_only"
    if annotatable:
        candidates = [
            line for line in lines if m.window_start <= line.occurred_on <= ctx.today and det.match_line(line, spec)
        ]
        ages = sorted((ctx.today - line.occurred_on).days for line in m.matched)
        median_age = ages[len(ages) // 2]
        factors.append(
            XAIFactor(
                label="Receipts recorded",
                detail=(
                    f"{len(m.matched)} of {len(candidates)} matching expenses have no receipt recorded, worth "
                    f"{display.format(m.observed_krw)}. The oldest is {ages[-1]} days old; the median is {median_age} "
                    "days old. Tick an expense below once you have its receipt."
                ),
                value=float(m.observed_krw),
            )
        )

    factors.append(coverage_factor(coverage, ctx.today))
    return _flag(
        spec,
        c.severity,
        factors,
        jurisdiction,
        exposure_ratio=m.exposure_ratio,
        observed_krw=m.observed_krw,
        assumed_threshold_krw=rule.threshold_krw,
        assumption_source=rule.assumption_source,
        evidence=_evidence(m.matched),
        annotatable=annotatable,
        **fields,
    )


def _evaluate_single_line(
    rule: EffectiveRule,
    lines: Sequence[det.LedgerLine],
    ctx: det.EvalContext,
    display: DisplayCurrency,
    coverage: LedgerCoverage,
    jurisdiction: str | None,
) -> RuleOutcome:
    spec = rule.spec
    m = det.measure_single_line(spec, list(lines), ctx, rule.threshold_krw)
    if m is None:
        return _suppress(spec, SuppressionReason.NO_MATCHING_TRANSACTIONS, f"Meika found no {spec.match_description}.")
    c = det.classify_single_line(m, ctx, spec.max_severity)
    if c.severity is None:
        return _suppress(
            spec,
            SuppressionReason.BELOW_EMISSION_BAND,
            f"The largest matching transaction is {display.format(m.largest_amount)}, against an assumed "
            f"{display.format(m.threshold)} ({_pct(m.exposure_ratio)}).",
        )
    spread_note = (
        f" Because your matching transactions vary by {display.format(m.spread)}, one about that much larger would "
        "reach the assumed figure, so this is a 'watch'."
        if c.path == "watch"
        else ""
    )
    factors = [
        XAIFactor(
            label="Largest matching transaction",
            detail=(
                f"Your largest single matching transaction is {display.format(m.largest_amount)} "
                f"('{m.largest.title}', {_day(m.largest.occurred_on)}), out of {len(m.matched)} in the last 12 months."
                f"{spread_note}"
            ),
            value=float(m.largest_amount),
        ),
        _assumption_factor(rule, display),
        coverage_factor(coverage, ctx.today),
    ]
    return _flag(
        spec,
        c.severity,
        factors,
        jurisdiction,
        exposure_ratio=m.exposure_ratio,
        observed_krw=m.largest_amount,
        assumed_threshold_krw=rule.threshold_krw,
        assumption_source=rule.assumption_source,
        crossed_on=m.largest.occurred_on if c.path == "crossed" else None,
        evidence=_evidence(m.matched),
    )


def _evaluate_footprint(
    rule: EffectiveRule,
    lines: Sequence[det.LedgerLine],
    ctx: det.EvalContext,
    display: DisplayCurrency,
    coverage: LedgerCoverage,
    jurisdiction: str | None,
) -> RuleOutcome:
    spec = rule.spec
    m = det.measure_currency_footprint(spec, list(lines), ctx)
    if m is None:
        return _suppress(spec, SuppressionReason.NO_MATCHING_TRANSACTIONS, f"Meika found no {spec.match_description}.")
    c = det.classify_currency_footprint(m, spec.max_severity)
    summary = (
        f"{len(m.currencies)} foreign currenc{'y' if len(m.currencies) == 1 else 'ies'}, {_pct(m.share)} of spending, "
        f"across {m.months_spanned} month(s)"
    )
    if c.severity is None:
        return _suppress(
            spec,
            SuppressionReason.BELOW_EMISSION_BAND,
            f"{m.conditions_met} of 3 pattern conditions met ({summary}).",
        )
    factors = [
        XAIFactor(
            label="Currencies in your ledger",
            detail=(
                f"In the last 12 months you logged spending in {len(m.currencies)} foreign "
                f"currenc{'y' if len(m.currencies) == 1 else 'ies'} ({', '.join(m.currencies)}) across "
                f"{m.months_spanned} month(s), {m.sustained_months} of them above a {_pct(m.min_share)} share. "
                f"Foreign-currency spending is {_pct(m.share)} of the total ({display.format(m.foreign_total_krw)} of "
                f"{display.format(m.total_krw)}). This says nothing about where you are resident, which usually "
                "depends on days present."
            ),
            value=float(m.share * 100),
        ),
        XAIFactor(
            label="The pattern Meika is assuming",
            detail=f"{spec.assumption_statement} {spec.source_note} {spec.verification_prompt}",
            value=float(m.conditions_met),
        ),
        coverage_factor(coverage, ctx.today),
    ]
    return _flag(
        spec,
        c.severity,
        factors,
        jurisdiction,
        exposure_ratio=m.share,
        observed_krw=m.foreign_total_krw,
        assumed_threshold_krw=None,
        assumption_source=None,
        evidence=_evidence(m.foreign),
    )


def _evaluate_recurring(
    rule: EffectiveRule,
    lines: Sequence[det.LedgerLine],
    ctx: det.EvalContext,
    display: DisplayCurrency,
    coverage: LedgerCoverage,
    jurisdiction: str | None,
) -> RuleOutcome:
    spec = rule.spec
    min_annual = Decimal(str(spec.params.get("min_annual_krw", "1200000")))
    groups = det.measure_recurring(spec, list(lines), ctx)
    c = det.classify_recurring(groups, min_annual, spec.max_severity)
    if c.severity is None:
        return _suppress(spec, SuppressionReason.NO_MATCHING_TRANSACTIONS, f"Meika found no {spec.match_description}.")
    factors = [
        XAIFactor(
            label=f"'{g.label}' repeats",
            detail=(
                f"'{g.label}' has recurred {len(g.lines)} times about every {g.median_gap} days, median "
                f"{display.format(g.median_amount)} (amounts vary by {_pct(g.variability)}). At that pace "
                f"{display.format(g.amount_in_current_fy)} falls inside the tax year ending {_day(ctx.fiscal.end)}, and "
                f"a payment of about {display.format(g.spills_into_next_fy)} falls on {_day(g.next_after_fy_end)}, "
                f"after it. That is {display.format(g.annualized)} a year."
            ),
            value=float(g.annualized),
        )
        for g in groups[:3]
    ]
    factors.append(
        XAIFactor(
            label="The figure Meika is assuming",
            detail=f"{spec.assumption_statement} {spec.source_note} {spec.verification_prompt}",
            value=float(min_annual),
        )
    )
    factors.append(coverage_factor(coverage, ctx.today))
    top = groups[0]
    return _flag(
        spec,
        c.severity,
        factors,
        jurisdiction,
        exposure_ratio=(top.annualized / min_annual).quantize(Decimal("0.0001")),
        observed_krw=top.annualized,
        assumed_threshold_krw=min_annual,
        assumption_source=None,
        evidence=_evidence([line for g in groups for line in g.lines]),
    )


# --- whole-ledger evaluation --------------------------------------------


def evaluate_ledger(
    *,
    lines: Sequence[det.LedgerLine],
    ctx: det.EvalContext,
    ruleset: Ruleset,
    overrides: Mapping[str, Any],
    display: DisplayCurrency,
    expense_count: int,
    residence_jurisdiction: str | None = None,
    bands: det.BandConfig = det.DEFAULT_BANDS,
) -> ComplianceForesightResult:
    lines = [line for line in lines if line.occurred_on <= ctx.today]
    coverage = LedgerCoverage(
        expense_count=expense_count,
        first_day=ctx.ledger_first_day,
        ledger_days=ctx.ledger_days,
        cannot_see=CANNOT_SEE,
    )

    flags: list[ComplianceFlag] = []
    suppressed: list[SuppressedRule] = []
    for spec in ruleset.rules:
        rule = effective_rule(spec, overrides.get(spec.rule_key))
        outcome = _evaluate_rule(rule, lines, ctx, display, bands, coverage, residence_jurisdiction)
        if outcome.flag:
            flags.append(outcome.flag)
        else:
            suppressed.append(outcome.suppressed)
    for invalid in ruleset.invalid:
        suppressed.append(
            SuppressedRule(
                rule_key=invalid.rule_key,
                title=invalid.title,
                reason=SuppressionReason.RULE_SPEC_INVALID,
                detail=f"This rule's definition failed validation and was skipped: {invalid.error}",
            )
        )

    flags.sort(key=lambda f: (-det.SEVERITY_RANK[f.severity], -f.exposure_ratio, f.rule_key))
    counts = ComplianceCounts(
        high=sum(1 for f in flags if f.severity == RiskLevel.HIGH),
        moderate=sum(1 for f in flags if f.severity == RiskLevel.MODERATE),
        low=sum(1 for f in flags if f.severity == RiskLevel.LOW),
        rules_evaluated=len(ruleset.rules) + len(ruleset.invalid),
        rules_suppressed=len(suppressed),
    )
    return ComplianceForesightResult(
        as_of=ctx.today,
        flags=flags,
        suppressed=suppressed,
        counts=counts,
        coverage=coverage,
        fiscal_window=FiscalWindowRead(
            start=ctx.fiscal.start,
            end=ctx.fiscal.end,
            days_remaining=ctx.days_remaining_fy,
            is_default=ctx.fiscal.is_default,
        ),
        disclaimer=DISCLAIMER,
        rules_version=ruleset.version,
    )


def _evaluate_rule(
    rule: EffectiveRule,
    lines: Sequence[det.LedgerLine],
    ctx: det.EvalContext,
    display: DisplayCurrency,
    bands: det.BandConfig,
    coverage: LedgerCoverage,
    jurisdiction: str | None,
) -> RuleOutcome:
    spec = rule.spec
    if not rule.is_enabled:
        return _suppress(spec, SuppressionReason.RULE_DISABLED_BY_USER, "You turned this rule off.")
    if coverage.expense_count == 0:
        return _suppress(
            spec, SuppressionReason.NO_LEDGER, "You haven't logged any expenses yet, so there is nothing to compare."
        )
    required = _REQUIRED_DAYS.get(spec.detector_kind)
    if required and ctx.ledger_days < required:
        return _suppress(
            spec,
            SuppressionReason.INSUFFICIENT_HISTORY,
            f"Meika has {ctx.ledger_days} day(s) of logged history; this rule needs {required}.",
            days_observed=ctx.ledger_days,
            days_required=required,
        )

    kind = spec.detector_kind
    if kind == ComplianceDetectorKind.THRESHOLD_ACCUMULATION:
        return _evaluate_accumulation(rule, lines, ctx, display, bands, coverage, jurisdiction)
    if kind == ComplianceDetectorKind.SINGLE_LINE_THRESHOLD:
        return _evaluate_single_line(rule, lines, ctx, display, coverage, jurisdiction)
    if kind == ComplianceDetectorKind.CURRENCY_FOOTPRINT:
        return _evaluate_footprint(rule, lines, ctx, display, coverage, jurisdiction)
    return _evaluate_recurring(rule, lines, ctx, display, coverage, jurisdiction)
