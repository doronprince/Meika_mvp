import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.models.enums import ExpenseCategory
from app.schemas.common import RiskLevel, XAIFactor

MAX_HORIZON_MONTHS = 120
# Exact Shapley attribution simulates every subset of shocks: 2^8 = 256 runs
# of at most 120 months is milliseconds; past that it grows fast for no
# explanatory gain — nobody reads a nine-way attribution.
MAX_SHOCKS = 8


class _ShockBase(BaseModel):
    label: str | None = Field(default=None, max_length=80)


class IncomeLossShock(_ShockBase):
    kind: Literal["income_loss"] = "income_loss"
    pct: Decimal = Field(gt=0, le=100)
    # None = every active income stream.
    income_stream_id: uuid.UUID | None = None
    start_month: int = Field(default=1, ge=1, le=MAX_HORIZON_MONTHS)
    # None = permanent.
    duration_months: int | None = Field(default=None, ge=1, le=MAX_HORIZON_MONTHS)


class ExpenseIncreaseShock(_ShockBase):
    kind: Literal["expense_increase"] = "expense_increase"
    pct: Decimal = Field(gt=0, le=500)
    # None = every essential category.
    category: ExpenseCategory | None = None
    start_month: int = Field(default=1, ge=1, le=MAX_HORIZON_MONTHS)
    duration_months: int | None = Field(default=None, ge=1, le=MAX_HORIZON_MONTHS)


class CurrencyDevaluationShock(_ShockBase):
    """The named currency loses `pct` percent of its value against KRW.
    Affects only income streams paid in that currency."""

    kind: Literal["currency_devaluation"] = "currency_devaluation"
    currency: str = Field(min_length=3, max_length=3)
    pct: Decimal = Field(gt=0, lt=100)
    start_month: int = Field(default=1, ge=1, le=MAX_HORIZON_MONTHS)


class OneOffExpenseShock(_ShockBase):
    kind: Literal["one_off_expense"] = "one_off_expense"
    amount_krw: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    month: int = Field(default=1, ge=1, le=MAX_HORIZON_MONTHS)


class InflationShock(_ShockBase):
    """Compounding annual price growth on essential categories only."""

    kind: Literal["inflation"] = "inflation"
    annual_pct: Decimal = Field(gt=0, le=100)
    start_month: int = Field(default=1, ge=1, le=MAX_HORIZON_MONTHS)


Shock = Annotated[
    Union[IncomeLossShock, ExpenseIncreaseShock, CurrencyDevaluationShock, OneOffExpenseShock, InflationShock],
    Field(discriminator="kind"),
]


class SurvivalSimulationRequest(BaseModel):
    shocks: list[Shock] = Field(default_factory=list, max_length=MAX_SHOCKS)
    horizon_months: int = Field(default=60, ge=6, le=MAX_HORIZON_MONTHS)
    # The "with cuts" runway: discretionary categories are cut by this much
    # once savings fall below cut_trigger_buffer_months of essential spend.
    discretionary_cut_pct: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    cut_trigger_buffer_months: Decimal = Field(default=Decimal("3"), ge=0, le=24)


class SurvivalState(str, enum.Enum):
    COMPUTED = "computed"
    # No liquid_savings_krw on the profile: the spend/income baseline is
    # still reported, but no runway is invented without a starting balance.
    NEEDS_SAVINGS = "needs_savings"


class CategoryBaseline(BaseModel):
    # None = the unclassified monthly-budget baseline used before any
    # expenses are logged; treated as essential.
    category: ExpenseCategory | None
    monthly_krw: Decimal
    essential: bool


class SpendBaseline(BaseModel):
    monthly_income_krw: Decimal
    monthly_essential_krw: Decimal
    monthly_discretionary_krw: Decimal
    monthly_net_krw: Decimal
    spend_source: Literal["ledger", "monthly_budget"]
    ledger_days: int
    income_streams_counted: int
    categories: list[CategoryBaseline]


class Runway(BaseModel):
    # None when savings never run out within the horizon.
    months: float | None
    days: int | None
    sustainable_within_horizon: bool


class ShockAttribution(BaseModel):
    shock_index: int
    label: str
    kind: str
    # Exact Shapley value: this shock's average marginal runway loss over
    # every order the shocks could arrive in. Sums to the joint loss.
    months_lost: float
    # Runway loss if this were the only shock.
    standalone_months_lost: float
    share_pct: float | None


class TrajectoryPoint(BaseModel):
    month: int
    baseline_balance_krw: Decimal
    shocked_balance_krw: Decimal
    shocked_with_cuts_balance_krw: Decimal


class SurvivalReport(BaseModel):
    """`factors` carries the arithmetic behind every runway figure — see the
    XAI-enforcement guardrail."""

    state: SurvivalState
    as_of: date
    horizon_months: int
    liquid_savings_krw: Decimal | None
    baseline: SpendBaseline
    baseline_runway: Runway | None
    shocked_runway: Runway | None
    shocked_with_cuts_runway: Runway | None
    cuts_start_month: int | None
    risk_level: RiskLevel | None
    attributions: list[ShockAttribution]
    joint_months_lost: float | None
    interaction_months: float | None
    attribution_residual_months: float | None
    trajectory: list[TrajectoryPoint]
    factors: list[XAIFactor]
    assumptions: list[str]


class ShockPreset(BaseModel):
    key: str
    title: str
    description: str
    shock: Shock
