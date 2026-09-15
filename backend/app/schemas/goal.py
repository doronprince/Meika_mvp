import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ExpenseCategory, GoalType
from app.schemas.common import XAIFactor


class GoalVerdict(str, enum.Enum):
    """Computed on every read from real contributions / expenses, never stored."""

    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"
    ACHIEVED = "achieved"
    MISSED = "missed"
    INSUFFICIENT_DATA = "insufficient_data"


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    goal_type: GoalType
    target_amount_krw: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    starting_amount_krw: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    category: ExpenseCategory | None = None
    # Omitted = today (resolved in the service layer).
    start_date: date | None = None
    target_date: date

    @model_validator(mode="after")
    def _consistent_with_goal_type(self):
        start = self.start_date or date.today()
        if self.target_date < start:
            raise ValueError("target_date must be on or after start_date")
        if self.goal_type == GoalType.SAVINGS and self.category is not None:
            raise ValueError("category only applies to spending_cap goals")
        if self.goal_type == GoalType.SPENDING_CAP and self.starting_amount_krw != 0:
            raise ValueError("starting_amount_krw only applies to savings goals")
        return self


class GoalContributionCreate(BaseModel):
    # Negative = a withdrawal from the savings pot.
    amount_krw: Decimal = Field(max_digits=12, decimal_places=2)
    contributed_on: date | None = None
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _non_zero(self):
        if self.amount_krw == 0:
            raise ValueError("amount_krw must be non-zero")
        return self


class GoalContributionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount_krw: Decimal
    contributed_on: date
    note: str | None
    created_at: datetime


class GoalForecast(BaseModel):
    """Every number here is recomputable by hand from the goal and its
    progress — see app/services/goal_forecast.py. `factors` is the reasoning
    behind `verdict`; never render one without the other (XAI guardrail)."""

    verdict: GoalVerdict
    progress_krw: Decimal
    progress_percent: Decimal
    days_elapsed: int
    days_total: int
    days_remaining: int
    pace_krw_per_day: Decimal
    projected_final_krw: Decimal | None
    projected_percent_of_target: Decimal | None
    # The counterfactual: the daily rate that exactly lands on target, and how
    # far the current pace is from it (positive = behaviour must change).
    required_krw_per_day: Decimal | None
    required_change_krw_per_day: Decimal | None
    factors: list[XAIFactor]


class GoalRead(BaseModel):
    id: uuid.UUID
    name: str
    goal_type: GoalType
    target_amount_krw: Decimal
    starting_amount_krw: Decimal
    category: ExpenseCategory | None
    start_date: date
    target_date: date
    created_at: datetime
    forecast: GoalForecast
