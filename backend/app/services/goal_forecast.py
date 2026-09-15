"""Explainable goal forecasting (Review-1 Objectives 3 & 4, research Gap 5).

Pure and synchronous — no database, no I/O — so every verdict can be unit
tested and recomputed by hand from its inputs: target, opening amount,
progress, and the start / target / current dates.

Model: the average daily pace since the goal started, projected over the
remaining days. Deliberately the simplest pace model that can be audited;
scripts/eval_goal_forecast.py measures it against naive baselines instead of
assuming it is good.

Verdict semantics are defined by the counterfactual itself, so a verdict and
its explanation can never disagree:
- ON_TRACK  — the projection meets the target (or stays under the cap).
- AT_RISK   — it doesn't, but changing the current pace by at most
              AT_RISK_MAX_PACE_CHANGE closes the gap.
- OFF_TRACK — closing the gap needs a bigger change than that.
Too little history for a projection -> INSUFFICIENT_DATA, reusing the
dashboard's warm-up window (see [[dashboard-projection-warmup]]).
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.models.enums import ExpenseCategory, GoalType
from app.schemas.common import XAIFactor
from app.schemas.goal import GoalForecast, GoalVerdict
from app.services.currency_display import DisplayCurrency
from app.services.dashboard_service import MIN_DAYS_FOR_PROJECTION

# A pace change of up to a quarter (e.g. skipping one café visit in four) is
# treated as a closable gap; beyond that the plan itself likely needs
# revisiting. An explicit assumption, not a fitted value — the evaluation
# script reports how verdicts shift when it moves.
AT_RISK_MAX_PACE_CHANGE = Decimal("0.25")

_CENTS = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _scope_label(category: ExpenseCategory | None) -> str:
    if category is None:
        return "all spending"
    return f"{category.value.replace('_', ' ').title()} spending"


def forecast_goal(
    *,
    goal_type: GoalType,
    target_krw: Decimal,
    start_date: date,
    target_date: date,
    today: date,
    progress_krw: Decimal,
    display: DisplayCurrency,
    starting_krw: Decimal = Decimal("0"),
    category: ExpenseCategory | None = None,
) -> GoalForecast:
    is_savings = goal_type == GoalType.SAVINGS
    fmt = display.format

    days_total = (target_date - start_date).days + 1
    days_elapsed = 0 if today < start_date else (min(today, target_date) - start_date).days + 1
    days_remaining = max(0, (target_date - max(today, start_date - timedelta(days=1))).days)

    progress = _q2(progress_krw)
    progress_percent = _q2(progress / target_krw * Decimal(100))
    # The opening amount counts toward progress but wasn't earned at the
    # current pace, so it's excluded from the pace itself.
    paced_amount = progress - starting_krw if is_savings else progress
    pace = _q2(paced_amount / Decimal(days_elapsed)) if days_elapsed else Decimal("0.00")

    factors: list[XAIFactor] = []
    if is_savings:
        opening = f" (including {fmt(starting_krw)} set aside at the start)" if starting_krw > 0 else ""
        factors.append(
            XAIFactor(
                label="Progress toward target",
                detail=(
                    f"Saved {fmt(progress)} of {fmt(target_krw)} ({progress_percent}%){opening} — "
                    f"day {days_elapsed} of {days_total}."
                ),
                value=float(progress_percent),
            )
        )
    else:
        factors.append(
            XAIFactor(
                label="Spending against cap",
                detail=(
                    f"Spent {fmt(progress)} of a {fmt(target_krw)} cap on {_scope_label(category)}, including "
                    f"transit costs ({progress_percent}%) — day {days_elapsed} of {days_total}."
                ),
                value=float(progress_percent),
            )
        )

    projected: Decimal | None = None
    projected_percent: Decimal | None = None
    required: Decimal | None = None
    change: Decimal | None = None

    if today < start_date:
        verdict = GoalVerdict.INSUFFICIENT_DATA
        factors.append(
            XAIFactor(label="Goal has not started", detail=f"Tracking starts on {start_date.isoformat()}.", value=None)
        )
    elif is_savings and progress >= target_krw:
        verdict = GoalVerdict.ACHIEVED
        factors.append(
            XAIFactor(
                label="Target reached",
                detail=f"Saved {fmt(progress)} against a {fmt(target_krw)} target.",
                value=float(progress),
            )
        )
    elif not is_savings and progress > target_krw:
        verdict = GoalVerdict.MISSED
        factors.append(
            XAIFactor(
                label="Cap exceeded",
                detail=f"Spent {fmt(progress - target_krw)} more than the {fmt(target_krw)} cap.",
                value=float(progress - target_krw),
            )
        )
    elif today > target_date:
        if is_savings:
            verdict = GoalVerdict.MISSED
            factors.append(
                XAIFactor(
                    label="Target date passed",
                    detail=f"Finished {fmt(target_krw - progress)} short of the target on {target_date.isoformat()}.",
                    value=float(target_krw - progress),
                )
            )
        else:
            verdict = GoalVerdict.ACHIEVED
            factors.append(
                XAIFactor(
                    label="Stayed within cap",
                    detail=f"Finished at {fmt(progress)} of the {fmt(target_krw)} cap on {target_date.isoformat()}.",
                    value=float(progress),
                )
            )
    else:
        factors.append(
            XAIFactor(
                label="Current pace",
                detail=(
                    f"{'Saving' if is_savings else 'Spending'} an average of {fmt(pace)}/day "
                    f"since {start_date.isoformat()}."
                ),
                value=float(pace),
            )
        )

        if days_remaining > 0:
            # Savings: what's still to save. Caps: what's still allowed.
            required = _q2((target_krw - progress) / Decimal(days_remaining))
            change = required - pace if is_savings else pace - required

        if days_elapsed < MIN_DAYS_FOR_PROJECTION:
            verdict = GoalVerdict.INSUFFICIENT_DATA
            factors.append(
                XAIFactor(
                    label="Projection not yet available",
                    detail=(
                        f"Only {days_elapsed} day(s) of history — a pace-based projection needs at least "
                        f"{MIN_DAYS_FOR_PROJECTION} days to be meaningful."
                    ),
                    value=None,
                )
            )
        else:
            projected = _q2(progress + pace * Decimal(days_remaining))
            projected_percent = _q2(projected / target_krw * Decimal(100))
            meets = projected >= target_krw if is_savings else projected <= target_krw
            if meets:
                verdict = GoalVerdict.ON_TRACK
            elif change is not None and pace > 0 and change / pace <= AT_RISK_MAX_PACE_CHANGE:
                verdict = GoalVerdict.AT_RISK
            else:
                verdict = GoalVerdict.OFF_TRACK

            if is_savings:
                label = "Projected to reach target" if meets else "Projected to fall short"
            else:
                label = "Projected to stay under cap" if meets else "Projected to exceed cap"
            factors.append(
                XAIFactor(
                    label=label,
                    detail=(
                        f"At {fmt(pace)}/day for the remaining {days_remaining} day(s), you finish at "
                        f"{fmt(projected)} ({projected_percent}% of the {'target' if is_savings else 'cap'})."
                    ),
                    value=float(projected),
                )
            )

        if required is not None and change is not None:
            factors.append(
                _counterfactual_factor(
                    is_savings=is_savings,
                    required=required,
                    change=change,
                    pace=pace,
                    days_remaining=days_remaining,
                    category=category,
                    verdict=verdict,
                    display=display,
                )
            )

    return GoalForecast(
        verdict=verdict,
        progress_krw=progress,
        progress_percent=progress_percent,
        days_elapsed=days_elapsed,
        days_total=days_total,
        days_remaining=days_remaining,
        pace_krw_per_day=pace,
        projected_final_krw=projected,
        projected_percent_of_target=projected_percent,
        required_krw_per_day=required,
        required_change_krw_per_day=change,
        factors=factors,
    )


def _counterfactual_factor(
    *,
    is_savings: bool,
    required: Decimal,
    change: Decimal,
    pace: Decimal,
    days_remaining: int,
    category: ExpenseCategory | None,
    verdict: GoalVerdict,
    display: DisplayCurrency,
) -> XAIFactor:
    fmt = display.format
    relative = f" ({change / pace * 100:.0f}% of your current pace)" if pace > 0 and change > 0 else ""
    band = (
        f" A change of up to {AT_RISK_MAX_PACE_CHANGE * 100:.0f}% of pace counts as at-risk rather than off-track."
        if verdict in (GoalVerdict.AT_RISK, GoalVerdict.OFF_TRACK)
        else ""
    )
    if is_savings:
        if change > 0:
            return XAIFactor(
                label="What would fix it",
                detail=(
                    f"Saving {fmt(required)}/day ({fmt(required * 7)}/week) for the remaining {days_remaining} "
                    f"day(s) reaches the target — {fmt(change)}/day more than now{relative}.{band}"
                ),
                value=float(change),
            )
        return XAIFactor(
            label="Margin",
            detail=f"Reaching the target needs {fmt(required)}/day; your pace is {fmt(-change)}/day ahead of that.",
            value=float(change),
        )
    if change > 0:
        return XAIFactor(
            label="What would fix it",
            detail=(
                f"Keeping {_scope_label(category)} under {fmt(required)}/day for the remaining {days_remaining} "
                f"day(s) stays within the cap — cut {fmt(change)}/day ({fmt(change * 7)}/week){relative}.{band}"
            ),
            value=float(change),
        )
    return XAIFactor(
        label="Headroom",
        detail=(
            f"You can spend up to {fmt(required)}/day on {_scope_label(category)} and stay under the cap; "
            f"you're {fmt(-change)}/day below that."
        ),
        value=float(change),
    )
