import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import AssumptionSource
from app.schemas.common import RiskLevel, XAIFactor


class ComplianceDetectorKind(str, enum.Enum):
    """Which arithmetic a rule runs. Rules pick one of these in
    app/data/compliance_rules.json; no detector has a rule-specific branch."""

    THRESHOLD_ACCUMULATION = "threshold_accumulation"
    SINGLE_LINE_THRESHOLD = "single_line_threshold"
    CURRENCY_FOOTPRINT = "currency_footprint"
    RECURRING_BOUNDARY = "recurring_boundary"


class SuppressionReason(str, enum.Enum):
    """Why a rule produced no flag. Computed on every read, never stored —
    same precedent as PriceTrendResult."""

    NO_LEDGER = "no_ledger"
    INSUFFICIENT_HISTORY = "insufficient_history"
    NO_MATCHING_TRANSACTIONS = "no_matching_transactions"
    BELOW_EMISSION_BAND = "below_emission_band"
    RULE_DISABLED_BY_USER = "rule_disabled_by_user"
    RULE_SPEC_INVALID = "rule_spec_invalid"


class FlagEvidenceItem(BaseModel):
    expense_id: uuid.UUID | None
    occurred_on: date
    title: str
    amount_krw: Decimal
    original_currency: str | None
    original_amount: Decimal | None
    has_documentation: bool


class ComplianceFlag(BaseModel):
    """A POSSIBLE issue, never a finding. `factors` always ends with the
    professional-referral factor, appended in code — see [[no-tax-advice]]."""

    rule_key: str
    title: str
    question: str
    severity: RiskLevel
    exposure_ratio: Decimal
    observed_krw: Decimal | None
    assumed_threshold_krw: Decimal | None
    assumption_source: AssumptionSource | None
    crossed_on: date | None = None
    cross_earliest_on: date | None = None
    cross_latest_on: date | None = None
    factors: list[XAIFactor]
    evidence: list[FlagEvidenceItem]
    # True when evidence rows can be marked as having a receipt, which is what
    # the undocumented-costs rule reads.
    annotatable: bool = False


class SuppressedRule(BaseModel):
    rule_key: str
    title: str
    reason: SuppressionReason
    detail: str
    days_observed: int | None = None
    days_required: int | None = None


class LedgerCoverage(BaseModel):
    expense_count: int
    first_day: date | None
    ledger_days: int
    cannot_see: list[str]


class FiscalWindowRead(BaseModel):
    start: date
    end: date
    days_remaining: int
    # True when the user hasn't set their tax year and Meika is assuming
    # 1 January - 31 December.
    is_default: bool


class ComplianceCounts(BaseModel):
    high: int
    moderate: int
    low: int
    rules_evaluated: int
    rules_suppressed: int


class ComplianceForesightResult(BaseModel):
    """Deliberately carries NO aggregate score: a single compliance number
    would imply an authoritative legal judgment Meika cannot make. Every rule
    appears exactly once, in `flags` or in `suppressed`."""

    as_of: date
    flags: list[ComplianceFlag]
    suppressed: list[SuppressedRule]
    counts: ComplianceCounts
    coverage: LedgerCoverage
    fiscal_window: FiscalWindowRead
    disclaimer: str
    rules_version: str


class ComplianceRuleView(BaseModel):
    """One rule as it applies to this user — the audit surface: every
    assumption the module holds, readable before any flag fires."""

    rule_key: str
    title: str
    question: str
    detector_kind: ComplianceDetectorKind
    effective_threshold_krw: Decimal | None
    packaged_threshold_krw: Decimal | None
    threshold_basis_note: str | None
    assumption_statement: str
    verification_prompt: str
    source_note: str
    assumption_source: AssumptionSource
    is_enabled: bool
    verified_at: datetime | None
    verified_note: str | None
    max_severity: RiskLevel


class ComplianceRuleOverrideUpdate(BaseModel):
    """Partial update. `is_enabled` and `assumption_source` are typed without
    `| None`: omitting them is a no-op, an explicit null is rejected.
    `threshold_amount_krw` is nullable on purpose — an explicit null resets
    the rule to its packaged default."""

    threshold_amount_krw: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    is_enabled: bool = None
    assumption_source: AssumptionSource = None
    verified_note: str | None = Field(default=None, max_length=500)


class ComplianceSettingsRead(BaseModel):
    residence_jurisdiction: str | None
    home_jurisdiction: str | None
    fiscal_year_start_month: int
    fiscal_year_start_day: int
    is_default: bool


class ComplianceSettingsUpdate(BaseModel):
    residence_jurisdiction: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    home_jurisdiction: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    fiscal_year_start_month: int = Field(default=None, ge=1, le=12)
    # Checked against the month when the tax year is computed (29 February
    # resolves to 28 February in a non-leap year), not here.
    fiscal_year_start_day: int = Field(default=None, ge=1, le=31)

    @field_validator("residence_jurisdiction", "home_jurisdiction")
    @classmethod
    def _uppercase(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ExpenseTaxAnnotationUpsert(BaseModel):
    expense_id: uuid.UUID
    has_documentation: bool
    document_ref: str | None = Field(default=None, max_length=255)


class ExpenseTaxAnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expense_id: uuid.UUID
    has_documentation: bool
    document_ref: str | None
    annotated_on: date
