import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExposureKind
from app.schemas.common import XAIFactor


class ExposureSessionCreate(BaseModel):
    occurred_on: date
    started_hour: int | None = Field(default=None, ge=0, le=23)
    platform: str = Field(min_length=1, max_length=60)
    kind: ExposureKind
    minutes: int = Field(ge=1, le=1440)
    note: str | None = Field(default=None, max_length=500)


class ExposureSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurred_on: date
    started_hour: int | None
    platform: str
    kind: ExposureKind
    minutes: int
    note: str | None
    created_at: datetime


class InsightState(str, enum.Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    COMPUTED = "computed"


class AssociationVerdict(str, enum.Enum):
    ASSOCIATION = "association"
    NO_CLEAR_ASSOCIATION = "no_clear_association"


class AssociationResult(BaseModel):
    """Spearman correlation between daily exposure minutes and discretionary
    spending, after removing each series' day-of-week means, with a
    one-sided circular-shift permutation p-value."""

    spearman_rho: float | None
    p_value: float | None
    n_days: int
    n_permutations: int


class LagResult(AssociationResult):
    lag_days: int


class KindResult(AssociationResult):
    kind: ExposureKind
    minutes_total: int
    days_with_exposure: int


class EffectSize(BaseModel):
    high_exposure_threshold_minutes: int
    high_days: int
    zero_days: int
    mean_spend_after_high_krw: Decimal
    mean_spend_after_zero_krw: Decimal
    difference_krw: Decimal


class Intervention(BaseModel):
    triggered: bool
    today_minutes: int
    threshold_minutes: int | None
    top_platform: str | None
    expected_extra_spend_krw: Decimal | None
    message: str
    suggestion: str | None


class ExposureInsightReport(BaseModel):
    as_of: date
    state: InsightState
    window_start: date | None
    tracked_days: int
    days_with_exposure: int
    minutes_logged: int
    verdict: AssociationVerdict | None
    primary: AssociationResult | None
    exploratory_lags: list[LagResult]
    by_kind: list[KindResult]
    effect: EffectSize | None
    intervention: Intervention
    factors: list[XAIFactor]
    limitations: list[str]
