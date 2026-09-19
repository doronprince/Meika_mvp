import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import RiskLevel, XAIFactor


class ClaimEvaluationRequest(BaseModel):
    claim_text: str = Field(min_length=10, max_length=500)
    # What the user is thinking of putting into this. In stake_currency, or
    # the user's preferred currency when that is omitted.
    stake_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    stake_currency: str | None = Field(default=None, min_length=3, max_length=3)
    # Two-letter country to search from; defaults from preferred_currency.
    country: str | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def _currency_needs_amount(self):
        if self.stake_currency is not None and self.stake_amount is None:
            raise ValueError("stake_currency needs stake_amount")
        return self


class ScorePart(BaseModel):
    label: str
    points: int


class SourceAssessment(BaseModel):
    position: int
    title: str
    link: str
    domain: str
    tier: str
    credibility: int
    credibility_parts: list[ScorePart]
    independence: int
    conflict_signals: list[ScorePart]
    date_known: bool
    age_days: int | None
    relevant: bool
    stance: str
    # Keyword matching over a search snippet, never a reading of the page.
    stance_method: str = "lexical"
    echo_of: int | None
    weight: float


class CautionComponent(BaseModel):
    key: str
    name: str
    cap: int
    points: float | None
    computable: bool
    detail: str


class PersonalContext(BaseModel):
    monthly_budget_krw: Decimal
    budget_headroom_krw: Decimal
    headroom_basis: str  # "projection" or "spend_to_date"
    spending_velocity_krw_per_day: Decimal
    budget_runway_days: float | None
    liquid_savings_krw: Decimal | None
    survival_runway_days: float | None
    exposure: float | None


class ClaimEvaluationReport(BaseModel):
    """CAUTION, NOT TRUTH: caution_score measures how much reason there is
    to be careful about acting on the claim given what could be retrieved.
    A low score never means the claim is correct ([[never-asserts-truth]])."""

    claim_text: str
    normalized_query: str
    country: str
    claim_type: str
    evidence_status: str
    evidence_fetched_at: datetime | None
    evidence_age_days: int | None
    evidence_stance: str
    caution_score: int | None
    # Equal to caution_score when a stake is given; otherwise the score if the
    # personal-exposure component were at its maximum.
    caution_score_upper: int | None
    risk_level: RiskLevel | None
    source_count: int
    usable_source_count: int
    weighted_credibility: float | None
    coi_density: float | None
    disagreement_index: float | None
    stake_amount_krw: Decimal | None
    stake_original_currency: str | None
    stake_original_amount: Decimal | None
    personal: PersonalContext
    components: list[CautionComponent]
    sources: list[SourceAssessment]
    factors: list[XAIFactor]
    limitations: list[str]
    disclaimer: str
    engine_version: str


class ClaimEvaluationRead(ClaimEvaluationReport):
    id: uuid.UUID
    created_at: datetime


class ClaimEvaluationSummary(BaseModel):
    id: uuid.UUID
    created_at: datetime
    claim_text: str
    claim_type: str
    evidence_stance: str
    caution_score: int | None
    caution_score_upper: int | None
    risk_level: RiskLevel | None
    source_count: int
