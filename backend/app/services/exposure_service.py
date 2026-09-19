"""Digital exposure vs spending, with a pre-emptive nudge.

Question: can a personal-finance system tell when digital or social exposure
goes with changes in spending, and step in before the damage is done?

What Meika can honestly see: screen time the user logs themselves
(exposure_sessions) and the expense ledger. It has no social-media or
app-usage API access, and this module never implies otherwise.

Method, fixed in advance so the result can't be tuned after the fact:

  * Daily series over the tracked period (first logged session, at most
    EXPOSURE_WINDOW_DAYS back): minutes of exposure, and discretionary spend
    (the same impulse-prone categories as the early-warning module).
  * ONE primary test: exposure on day d against discretionary spend on day
    d and d+1 combined. Purchases prompted by a feed can land the same day
    or the next; a single pre-specified window avoids the multiple-testing
    problem of shopping around between lags. Lags 0, 1 and 2 and per-kind
    results are shown too, labelled exploratory and uncorrected.
  * Both series have their day-of-week means removed first. Weekends are
    often busier for scrolling AND spending, and without this step that
    shared rhythm alone produces a correlation (scripts/eval_exposure.py
    measures how much).
  * Spearman rank correlation (spending is heavily skewed), with a one-sided
    p-value from circular-shift permutations: the exposure series is rotated
    against the spending series by every offset of at least MIN_SHIFT_DAYS,
    keeping each series' own autocorrelation, and p is the share of
    rotations that correlate at least as strongly. Exact and deterministic,
    no random seed.

Nudge: only when the primary test finds an association AND today's logged
exposure is in the user's own high range, with the money difference those
days have historically carried. Association, not causation — every surface
says so.
"""

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExposureKind
from app.models.expense import Expense
from app.models.exposure import ExposureSession
from app.models.user import User
from app.schemas.common import XAIFactor
from app.schemas.exposure import (
    AssociationResult,
    AssociationVerdict,
    EffectSize,
    ExposureInsightReport,
    ExposureSessionCreate,
    InsightState,
    Intervention,
    KindResult,
    LagResult,
)
from app.services.currency_display import DisplayCurrency, resolve_display_currency
from app.services.vulnerability_service import IMPULSE_CATEGORIES

EXPOSURE_WINDOW_DAYS = 90
MIN_TRACKED_DAYS = 28
MIN_EXPOSED_DAYS = 8
MIN_SHIFT_DAYS = 7  # a rotation shorter than a week would mostly compare a day with its neighbours
SIGNIFICANCE_LEVEL = 0.05
MIN_HIGH_EXPOSURE_MINUTES = 30
HIGH_EXPOSURE_QUANTILE = 2 / 3  # "high" = the top third of the user's own exposed days
MIN_EFFECT_GROUP_DAYS = 5
MIN_KIND_EXPOSED_DAYS = 4
EXPLORATORY_LAGS = (0, 1, 2)

LIMITATIONS = [
    "Association, not causation. Mood, boredom, payday or a stressful week can drive both screen time and "
    "spending; weekly rhythm is removed, other rhythms are not.",
    "Exposure is self-reported. Days with nothing logged are treated as zero exposure, so gaps in logging "
    "weaken any link Meika can find.",
    "Meika has no access to social-media or app-usage data. Everything here comes from what you logged.",
    f"With a few weeks of data, permutation p-values are coarse: with n days, the smallest possible p is "
    f"about 1/(n - {2 * MIN_SHIFT_DAYS}).",
    "Only the same-day-or-next-day test was fixed in advance. The per-lag and per-kind numbers are exploratory "
    "and not corrected for multiple comparisons.",
    "Discretionary spending means cafes & dining, apparel and electronics, the same impulse-prone set the early-"
    "warning module uses.",
]

_CENTS = Decimal("0.01")


def _dec(value: float) -> Decimal:
    return Decimal(repr(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Session:
    occurred_on: date
    minutes: int
    kind: ExposureKind
    platform: str


@dataclass(frozen=True)
class Spend:
    occurred_on: date
    value_krw: float
    discretionary: bool


def _ranks(values: list[float]) -> list[float]:
    """Average ranks (1-based), ties sharing the mean of their positions."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def _pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 3:
        return None
    mean_x, mean_y = sum(x) / n, sum(y) / n
    sxx = sum((a - mean_x) ** 2 for a in x)
    syy = sum((b - mean_y) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return None
    return sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y)) / (sxx * syy) ** 0.5


def _weekday_demeaned(values: list[float], days: list[date]) -> list[float]:
    totals: dict[int, list[float]] = defaultdict(list)
    for value, day in zip(values, days):
        totals[day.weekday()].append(value)
    means = {weekday: sum(v) / len(v) for weekday, v in totals.items()}
    return [value - means[day.weekday()] for value, day in zip(values, days)]


def association(
    x_values: list[float],
    x_days: list[date],
    y_values: list[float],
    y_days: list[date],
    *,
    demean: bool = True,
) -> AssociationResult:
    """x[i] is paired with y[i]. Returns Spearman rho on (optionally)
    weekday-demeaned series and a one-sided circular-shift permutation p."""
    n = len(x_values)
    x = _weekday_demeaned(x_values, x_days) if demean else list(x_values)
    y = _weekday_demeaned(y_values, y_days) if demean else list(y_values)
    rank_x, rank_y = _ranks(x), _ranks(y)
    observed = _pearson(rank_x, rank_y)
    shifts = list(range(MIN_SHIFT_DAYS, n - MIN_SHIFT_DAYS + 1))
    if observed is None or not shifts:
        return AssociationResult(spearman_rho=observed, p_value=None, n_days=n, n_permutations=0)

    at_least_as_strong = 0
    for shift in shifts:
        rotated = rank_x[shift:] + rank_x[:shift]
        rho = _pearson(rotated, rank_y)
        if rho is not None and rho >= observed - 1e-12:
            at_least_as_strong += 1
    p_value = (1 + at_least_as_strong) / (1 + len(shifts))
    return AssociationResult(
        spearman_rho=round(observed, 4), p_value=round(p_value, 4), n_days=n, n_permutations=len(shifts)
    )


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def compute_insights(
    sessions: list[Session],
    spends: list[Spend],
    *,
    as_of: date,
    display: DisplayCurrency,
) -> ExposureInsightReport:
    """Pure and point-in-time: nothing after `as_of` is read."""
    sessions = [s for s in sessions if s.occurred_on <= as_of]
    spends = [s for s in spends if s.occurred_on <= as_of]

    minutes_by_day: dict[date, int] = defaultdict(int)
    kind_minutes: dict[ExposureKind, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for s in sessions:
        minutes_by_day[s.occurred_on] += s.minutes
        kind_minutes[s.kind][s.occurred_on] += s.minutes
    today_minutes = minutes_by_day.get(as_of, 0)

    window_floor = as_of - timedelta(days=EXPOSURE_WINDOW_DAYS - 1)
    first_logged = min((s.occurred_on for s in sessions), default=None)
    window_start = max(first_logged, window_floor) if first_logged else None
    days = [window_start + timedelta(days=i) for i in range((as_of - window_start).days + 1)] if window_start else []
    exposure = [float(minutes_by_day.get(d, 0)) for d in days]
    exposed_days = sum(1 for m in exposure if m > 0)
    minutes_logged = int(sum(exposure))

    def empty_intervention(message: str) -> Intervention:
        return Intervention(
            triggered=False,
            today_minutes=today_minutes,
            threshold_minutes=None,
            top_platform=None,
            expected_extra_spend_krw=None,
            message=message,
            suggestion=None,
        )

    coverage = XAIFactor(
        label="Tracking coverage",
        detail=(
            f"{len(days)} day(s) tracked since {window_start:%d %b %Y}, {exposed_days} with logged screen time "
            f"({minutes_logged} minutes in total). Days with nothing logged count as zero exposure."
            if window_start
            else "No screen time logged yet."
        ),
        value=float(len(days)),
    )

    if len(days) < MIN_TRACKED_DAYS or exposed_days < MIN_EXPOSED_DAYS:
        detail = (
            f"This needs at least {MIN_TRACKED_DAYS} tracked days with screen time logged on {MIN_EXPOSED_DAYS} "
            f"or more of them; you have {len(days)} tracked day(s) and {exposed_days} with a session. With less, "
            "a correlation would mostly reflect chance, so none is reported."
        )
        return ExposureInsightReport(
            as_of=as_of,
            state=InsightState.INSUFFICIENT_DATA,
            window_start=window_start,
            tracked_days=len(days),
            days_with_exposure=exposed_days,
            minutes_logged=minutes_logged,
            verdict=None,
            primary=None,
            exploratory_lags=[],
            by_kind=[],
            effect=None,
            intervention=empty_intervention("Keep logging screen time; Meika needs a few weeks before it can look for a link."),
            factors=[coverage, XAIFactor(label="Not enough data yet", detail=detail, value=None)],
            limitations=LIMITATIONS,
        )

    spend_by_day: dict[date, float] = defaultdict(float)
    for s in spends:
        if s.discretionary:
            spend_by_day[s.occurred_on] += s.value_krw
    spend = [spend_by_day.get(d, 0.0) for d in days]

    # Primary: exposure on day d vs discretionary spend on d and d+1. The
    # last day has no "next day" yet, so it isn't paired.
    pair_days = days[:-1]
    pair_exposure = exposure[:-1]
    window_spend = [spend[i] + spend[i + 1] for i in range(len(days) - 1)]
    primary = association(pair_exposure, pair_days, window_spend, pair_days)
    found = (
        primary.spearman_rho is not None
        and primary.p_value is not None
        and primary.spearman_rho > 0
        and primary.p_value < SIGNIFICANCE_LEVEL
    )
    verdict = AssociationVerdict.ASSOCIATION if found else AssociationVerdict.NO_CLEAR_ASSOCIATION

    lags = []
    for lag in EXPLORATORY_LAGS:
        n = len(days) - lag
        result = association(exposure[:n], days[:n], spend[lag:], days[lag:])
        lags.append(LagResult(lag_days=lag, **result.model_dump()))

    by_kind = []
    for kind, per_day in sorted(kind_minutes.items(), key=lambda item: -sum(item[1].values())):
        series = [float(per_day.get(d, 0)) for d in pair_days]
        exposed = sum(1 for m in series if m > 0)
        if exposed < MIN_KIND_EXPOSED_DAYS:
            continue
        result = association(series, pair_days, window_spend, pair_days)
        by_kind.append(
            KindResult(kind=kind, minutes_total=int(sum(series)), days_with_exposure=exposed, **result.model_dump())
        )

    positive = [m for m in pair_exposure if m > 0]
    threshold = max(MIN_HIGH_EXPOSURE_MINUTES, round(_quantile(positive, HIGH_EXPOSURE_QUANTILE)))
    high = [window_spend[i] for i, m in enumerate(pair_exposure) if m >= threshold]
    zero = [window_spend[i] for i, m in enumerate(pair_exposure) if m == 0]
    effect = None
    if len(high) >= MIN_EFFECT_GROUP_DAYS and len(zero) >= MIN_EFFECT_GROUP_DAYS:
        mean_high, mean_zero = sum(high) / len(high), sum(zero) / len(zero)
        effect = EffectSize(
            high_exposure_threshold_minutes=threshold,
            high_days=len(high),
            zero_days=len(zero),
            mean_spend_after_high_krw=_dec(mean_high),
            mean_spend_after_zero_krw=_dec(mean_zero),
            difference_krw=_dec(mean_high - mean_zero),
        )

    high_days = {pair_days[i] for i, m in enumerate(pair_exposure) if m >= threshold}
    platform_minutes = Counter()
    for s in sessions:
        if s.occurred_on in high_days:
            platform_minutes[s.platform] += s.minutes
    top_platform = platform_minutes.most_common(1)[0][0] if platform_minutes else None

    factors = [coverage]
    rho_text = "n/a" if primary.spearman_rho is None else f"{primary.spearman_rho:.2f}"
    p_text = "n/a" if primary.p_value is None else f"{primary.p_value:.3f}"
    stats = (
        f"Spearman rho = {rho_text}, permutation p = {p_text} against {primary.n_permutations} time-shifted "
        f"comparisons, {primary.n_days} days"
    )
    if found:
        factors.append(
            XAIFactor(
                label="Screen time lines up with your spending",
                detail=f"On days with more logged exposure, your discretionary spending that day and the next tends to "
                f"be higher too ({stats}). Weekly rhythm was removed first, so busier weekends don't count. This is "
                "an association, not proof that one causes the other.",
                value=primary.spearman_rho,
            )
        )
    else:
        factors.append(
            XAIFactor(
                label="No clear link found",
                detail=f"Logged exposure and discretionary spending that day and the next don't move together more "
                f"than chance would produce ({stats}; a link needs p below {SIGNIFICANCE_LEVEL}).",
                value=primary.spearman_rho,
            )
        )

    if effect is not None:
        more_or_less = "more" if effect.difference_krw >= 0 else "less"
        factors.append(
            XAIFactor(
                label="After high-exposure days",
                detail=f"On the {effect.high_days} days with {threshold}+ minutes logged, discretionary spending that "
                f"day and the next averaged {display.format(effect.mean_spend_after_high_krw)}, vs "
                f"{display.format(effect.mean_spend_after_zero_krw)} after the {effect.zero_days} days with none: "
                f"{display.format(abs(effect.difference_krw))} {more_or_less}. {threshold} minutes is the top third "
                f"of your own exposed days (at least {MIN_HIGH_EXPOSURE_MINUTES}).",
                value=float(effect.difference_krw),
            )
        )
    else:
        factors.append(
            XAIFactor(
                label="Effect size not measurable yet",
                detail=f"Needs at least {MIN_EFFECT_GROUP_DAYS} high-exposure days ({threshold}+ minutes) and "
                f"{MIN_EFFECT_GROUP_DAYS} days with none; found {len(high)} and {len(zero)}.",
                value=None,
            )
        )

    lag_text = ", ".join(
        f"lag {r.lag_days}: rho {r.spearman_rho:.2f}" if r.spearman_rho is not None else f"lag {r.lag_days}: n/a"
        for r in lags
    )
    factors.append(
        XAIFactor(
            label="Exploratory: which day the spending lands",
            detail=f"Exposure vs discretionary spending the same day, one day and two days later ({lag_text}). Not "
            "corrected for multiple comparisons, so read these as hints only.",
            value=None,
        )
    )

    positive_effect = effect is not None and effect.difference_krw > 0
    if found and positive_effect and today_minutes >= threshold:
        platform_note = f", mostly on {top_platform}" if top_platform else ""
        intervention = Intervention(
            triggered=True,
            today_minutes=today_minutes,
            threshold_minutes=threshold,
            top_platform=top_platform,
            expected_extra_spend_krw=effect.difference_krw,
            message=f"You've logged {today_minutes} minutes today{platform_note}. On past days like this, your "
            f"discretionary spending over that day and the next ran {display.format(effect.difference_krw)} higher.",
            suggestion="Try a 24-hour pause on non-essential purchases: add anything you want to a wishlist and "
            "decide tomorrow.",
        )
    elif found and positive_effect:
        intervention = Intervention(
            triggered=False,
            today_minutes=today_minutes,
            threshold_minutes=threshold,
            top_platform=top_platform,
            expected_extra_spend_krw=effect.difference_krw,
            message=f"No nudge today ({today_minutes} minutes logged). Meika will nudge you on days you log "
            f"{threshold}+ minutes, when your spending has tended to run higher.",
            suggestion=None,
        )
    else:
        intervention = empty_intervention(
            "No nudge: Meika only steps in once your own history shows a link between screen time and spending."
        )
    factors.append(
        XAIFactor(
            label="Nudge today" if intervention.triggered else "No nudge today",
            detail=intervention.message + (f" {intervention.suggestion}" if intervention.suggestion else ""),
            value=float(today_minutes),
        )
    )

    return ExposureInsightReport(
        as_of=as_of,
        state=InsightState.COMPUTED,
        window_start=window_start,
        tracked_days=len(days),
        days_with_exposure=exposed_days,
        minutes_logged=minutes_logged,
        verdict=verdict,
        primary=primary,
        exploratory_lags=lags,
        by_kind=by_kind,
        effect=effect,
        intervention=intervention,
        factors=factors,
        limitations=LIMITATIONS,
    )


async def create_session(db: AsyncSession, user_id: uuid.UUID, data: ExposureSessionCreate) -> ExposureSession:
    session = ExposureSession(user_id=user_id, **data.model_dump())
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession, user_id: uuid.UUID, *, days: int = EXPOSURE_WINDOW_DAYS) -> list[ExposureSession]:
    since = date.today() - timedelta(days=days - 1)
    result = await db.execute(
        select(ExposureSession)
        .where(ExposureSession.user_id == user_id, ExposureSession.occurred_on >= since)
        .order_by(ExposureSession.occurred_on.desc(), ExposureSession.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_session(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(ExposureSession).where(ExposureSession.id == session_id, ExposureSession.user_id == user_id)
    )
    await db.commit()
    return result.rowcount > 0


async def insights_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, as_of: date | None = None
) -> ExposureInsightReport | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    as_of = as_of or date.today()
    since = as_of - timedelta(days=EXPOSURE_WINDOW_DAYS - 1)

    session_rows = await db.execute(
        select(ExposureSession).where(
            ExposureSession.user_id == user_id,
            ExposureSession.occurred_on >= since,
            ExposureSession.occurred_on <= as_of,
        )
    )
    expense_rows = await db.execute(
        select(Expense).where(Expense.user_id == user_id, Expense.occurred_on >= since, Expense.occurred_on <= as_of)
    )
    sessions = [Session(s.occurred_on, s.minutes, s.kind, s.platform) for s in session_rows.scalars()]
    spends = [
        Spend(e.occurred_on, float(e.amount_krw + e.transit_cost_krw), e.category in IMPULSE_CATEGORIES)
        for e in expense_rows.scalars()
    ]
    display = await resolve_display_currency(user.preferred_currency)
    return compute_insights(sessions, spends, as_of=as_of, display=display)


async def has_any_sessions(db: AsyncSession, user_id: uuid.UUID) -> bool:
    count = await db.execute(select(func.count()).select_from(ExposureSession).where(ExposureSession.user_id == user_id))
    return count.scalar_one() > 0
