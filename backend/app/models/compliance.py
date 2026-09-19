import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import AssumptionSource, enum_values


class UserComplianceProfile(UUIDPKMixin, TimestampMixin, Base):
    """Where the user files and when their tax year starts. At most one row
    per user; with no row Meika assumes a 1 January tax year and says so.
    Scoped by user_id per [[tenant-isolation]]."""

    __tablename__ = "user_compliance_profiles"
    __table_args__ = (
        CheckConstraint("fiscal_year_start_month BETWEEN 1 AND 12", name="fiscal_month_range"),
        CheckConstraint("fiscal_year_start_day BETWEEN 1 AND 31", name="fiscal_day_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    # ISO 3166-1 alpha-2. Used only to phrase the referral sentence — the
    # module holds no country-specific facts.
    residence_jurisdiction: Mapped[str | None] = mapped_column(String(2))
    home_jurisdiction: Mapped[str | None] = mapped_column(String(2))
    fiscal_year_start_month: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1", nullable=False)
    fiscal_year_start_day: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1", nullable=False)
    jurisdiction_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ComplianceRuleOverride(UUIDPKMixin, TimestampMixin, Base):
    """The only user-writable half of the rule system: a user's own figure
    for a rule, whether the rule is on, and where the figure came from. Rule
    structure lives in app/data/compliance_rules.json, never here."""

    __tablename__ = "compliance_rule_overrides"
    __table_args__ = (UniqueConstraint("user_id", "rule_key", name="uq_compliance_rule_overrides_user_id_rule_key"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # NULL = keep the packaged default.
    threshold_amount_krw: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    assumption_source: Mapped[AssumptionSource] = mapped_column(
        SAEnum(AssumptionSource, name="assumption_source", values_callable=enum_values),
        default=AssumptionSource.UNVERIFIED_DEFAULT,
        server_default=AssumptionSource.UNVERIFIED_DEFAULT.value,
        nullable=False,
    )
    # Records a claim the user made, not a verification Meika performed.
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_note: Mapped[str | None] = mapped_column(String(500))


class ExpenseTaxAnnotation(UUIDPKMixin, TimestampMixin, Base):
    """Whether the user holds a receipt for one of their expenses — read by
    the undocumented-costs rule. user_id duplicates expenses.user_id on
    purpose, so every annotation query filters on user_id directly; it is
    NOT a substitute for the ownership check on write."""

    __tablename__ = "expense_tax_annotations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    has_documentation: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # Free text the user types (e.g. "email from uni, 3 Mar"). Meika stores no files.
    document_ref: Mapped[str | None] = mapped_column(String(255))
    annotated_on: Mapped[date] = mapped_column(Date, nullable=False)
