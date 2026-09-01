import calendar
import uuid
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExpenseCategory
from app.models.expense import Expense
from app.models.user import User
from app.schemas.common import RiskLevel, XAIFactor
from app.schemas.dashboard import CategoryBreakdownItem, ClarityScore, DashboardSummary
from app.services.currency_display import DisplayCurrency, resolve_display_currency

# Below this many days of data, a projected month-end spend swings wildly on
# a single purchase (see [[dashboard-projection-warmup]]) — the factor is
# suppressed rather than shown with false confidence.
MIN_DAYS_FOR_PROJECTION = 7

_CENTS = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


async def get_dashboard_summary(
    db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None
) -> DashboardSummary | None:
    user = await db.get(User, user_id)
    if user is None:
        return None

    display = await resolve_display_currency(user.preferred_currency)
    today = today or date.today()
    first_of_month = date(today.year, today.month, 1)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day

    result = await db.execute(
        select(Expense).where(
            Expense.user_id == user_id,
            Expense.occurred_on >= first_of_month,
            Expense.occurred_on <= today,
        )
    )
    expenses = list(result.scalars().all())

    monthly_budget = user.monthly_budget_krw
    totals_by_category: dict[ExpenseCategory, Decimal] = defaultdict(lambda: Decimal("0"))
    total_spent = Decimal("0")
    for expense in expenses:
        line_total = expense.amount_krw + expense.transit_cost_krw
        total_spent += line_total
        totals_by_category[expense.category] += line_total

    category_breakdown = [
        CategoryBreakdownItem(
            category=category,
            total_krw=_q2(total),
            percent_of_spend=_q2(total / total_spent * Decimal(100)) if total_spent > 0 else Decimal("0.00"),
        )
        for category, total in totals_by_category.items()
    ]
    category_breakdown.sort(key=lambda item: item.total_krw, reverse=True)

    spending_velocity = _q2(total_spent / Decimal(days_elapsed))

    projected_month_end_spend: Decimal | None = None
    projected_overage: Decimal | None = None
    if days_elapsed >= MIN_DAYS_FOR_PROJECTION:
        projected_month_end_spend = _q2(spending_velocity * Decimal(days_in_month))
        projected_overage = max(Decimal("0.00"), _q2(projected_month_end_spend - monthly_budget))

    clarity_score = _compute_clarity_score(
        monthly_budget=monthly_budget,
        total_spent=total_spent,
        spending_velocity=spending_velocity,
        days_elapsed=days_elapsed,
        days_in_month=days_in_month,
        category_breakdown=category_breakdown,
        projected_month_end_spend=projected_month_end_spend,
        projected_overage=projected_overage,
        display=display,
    )

    return DashboardSummary(
        monthly_budget_krw=monthly_budget,
        total_spent_this_month_krw=_q2(total_spent),
        remaining_budget_krw=_q2(monthly_budget - total_spent),
        days_elapsed_this_month=days_elapsed,
        days_in_month=days_in_month,
        spending_velocity_krw_per_day=spending_velocity,
        projected_month_end_spend_krw=projected_month_end_spend,
        projected_overage_krw=projected_overage,
        category_breakdown=category_breakdown,
        clarity_score=clarity_score,
    )


def _compute_clarity_score(
    *,
    monthly_budget: Decimal,
    total_spent: Decimal,
    spending_velocity: Decimal,
    days_elapsed: int,
    days_in_month: int,
    category_breakdown: list[CategoryBreakdownItem],
    projected_month_end_spend: Decimal | None,
    projected_overage: Decimal | None,
    display: DisplayCurrency,
) -> ClarityScore:
    factors: list[XAIFactor] = []
    penalty = Decimal("0")

    # Early in the month, a single ordinary purchase looks like a huge
    # deviation from a smooth daily pace or a 100%-concentrated category —
    # not because the user is off track, but because the sample is tiny.
    # Dampen the pace and concentration penalties proportionally until
    # MIN_DAYS_FOR_PROJECTION days of data have accumulated, same warm-up
    # window the projection factor uses (see [[dashboard-projection-warmup]]).
    warmup = min(Decimal("1"), Decimal(days_elapsed) / Decimal(MIN_DAYS_FOR_PROJECTION))

    # Factor 1: pace against an even-spread budget, always computable.
    if monthly_budget > 0:
        expected_to_date = _q2(monthly_budget * Decimal(days_elapsed) / Decimal(days_in_month))
        pace_ratio = (total_spent / expected_to_date) if expected_to_date > 0 else Decimal("0")
        pace_penalty = min(Decimal("35"), max(Decimal("0"), (pace_ratio - Decimal("1")) * Decimal("35"))) * warmup
        penalty += pace_penalty
        warmup_note = "" if warmup == 1 else f" — early-month weighting applied ({warmup * 100:.0f}% of full penalty)"
        factors.append(
            XAIFactor(
                label="On pace with budget" if pace_penalty == 0 else "Spending ahead of even pace",
                detail=(
                    f"Spent {display.format(total_spent)} of an expected {display.format(expected_to_date)} "
                    f"by day {days_elapsed} of {days_in_month} "
                    f"({pace_ratio * 100:.0f}% of even-pace budget){warmup_note}."
                ),
                value=float(pace_ratio * 100),
            )
        )
    else:
        factors.append(
            XAIFactor(label="No monthly budget set", detail="Set a monthly budget to enable pace tracking.", value=None)
        )

    # Factor 2: projected month-end outcome, suppressed early in the month.
    if projected_month_end_spend is None:
        factors.append(
            XAIFactor(
                label="Projection not yet available",
                detail=(
                    f"Only {days_elapsed} day(s) of data this month — projection needs at least "
                    f"{MIN_DAYS_FOR_PROJECTION} days to be meaningful."
                ),
                value=None,
            )
        )
    else:
        overage = projected_overage or Decimal("0")
        overage_ratio = (overage / monthly_budget) if monthly_budget > 0 else Decimal("0")
        projection_penalty = min(Decimal("40"), overage_ratio * Decimal("100") * Decimal("0.4"))
        penalty += projection_penalty
        factors.append(
            XAIFactor(
                label="Projected to exceed budget" if overage > 0 else "Projected to stay within budget",
                detail=(
                    f"At the current pace of {display.format(spending_velocity)}/day, "
                    f"projected month-end spend is {display.format(projected_month_end_spend)} against a "
                    f"{display.format(monthly_budget)} budget"
                    + (f" (projected overage: {display.format(overage)})." if overage > 0 else ".")
                ),
                value=float(projected_month_end_spend),
            )
        )

    # Factor 3: category concentration.
    if total_spent > 0 and category_breakdown:
        top = category_breakdown[0]
        top_share = top.total_krw / total_spent
        concentration_penalty = (
            min(Decimal("15"), max(Decimal("0"), (top_share - Decimal("0.4")) * Decimal("25"))) * warmup
        )
        penalty += concentration_penalty
        warmup_note = "" if warmup == 1 else f" — early-month weighting applied ({warmup * 100:.0f}% of full penalty)"
        factors.append(
            XAIFactor(
                label="Spending is diversified across categories"
                if concentration_penalty == 0
                else "Spending is concentrated in one category",
                detail=(
                    f"{top.category.value.replace('_', ' ').title()} accounts for {top_share * 100:.0f}% of this "
                    f"month's spend ({display.format(top.total_krw)} of {display.format(total_spent)}){warmup_note}."
                ),
                value=float(top_share * 100),
            )
        )
    else:
        factors.append(
            XAIFactor(label="No spending recorded yet this month", detail="Log an expense to see category breakdown.", value=None)
        )

    score = max(0, min(100, round(100 - float(penalty))))
    if score >= 70:
        risk_level = RiskLevel.LOW
    elif score >= 40:
        risk_level = RiskLevel.MODERATE
    else:
        risk_level = RiskLevel.HIGH

    return ClarityScore(value=score, risk_level=risk_level, factors=factors)
