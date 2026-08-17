from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import ExpenseCategory
from app.schemas.common import RiskLevel, XAIFactor


class CategoryBreakdownItem(BaseModel):
    category: ExpenseCategory
    total_krw: Decimal
    percent_of_spend: Decimal


class ClarityScore(BaseModel):
    """0-100 Financial Clarity Score. `factors` is the full set of computed
    inputs behind `value` — see the XAI-enforcement guardrail: never render
    the score without the reasoning that produced it."""

    value: int
    risk_level: RiskLevel
    factors: list[XAIFactor]


class DashboardSummary(BaseModel):
    monthly_budget_krw: Decimal
    total_spent_this_month_krw: Decimal
    remaining_budget_krw: Decimal
    days_elapsed_this_month: int
    days_in_month: int
    spending_velocity_krw_per_day: Decimal
    projected_month_end_spend_krw: Decimal | None
    projected_overage_krw: Decimal | None
    category_breakdown: list[CategoryBreakdownItem]
    clarity_score: ClarityScore
