import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ExpenseCategory, GoalType, enum_values


class Goal(UUIDPKMixin, TimestampMixin, Base):
    """A user-owned savings target or spending cap with a deadline. Always
    scoped by user_id (see [[tenant-isolation]]). The forecast is computed
    on every read from real contributions / expenses and never stored —
    see app/services/goal_forecast.py."""

    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("target_amount_krw > 0", name="target_positive"),
        CheckConstraint("starting_amount_krw >= 0", name="starting_non_negative"),
        CheckConstraint("target_date >= start_date", name="dates_ordered"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    goal_type: Mapped[GoalType] = mapped_column(
        SAEnum(GoalType, name="goal_type", values_callable=enum_values), nullable=False
    )
    target_amount_krw: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Savings goals only: money already set aside before tracking began. Kept
    # apart from contributions so it counts toward progress without inflating
    # the saving pace the forecast projects forward.
    starting_amount_krw: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    # Spending caps only: restrict the cap to one category. NULL = all spending.
    category: Mapped[ExpenseCategory | None] = mapped_column(
        SAEnum(ExpenseCategory, name="expense_category", values_callable=enum_values)
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)

    contributions: Mapped[list["GoalContribution"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", passive_deletes=True
    )


class GoalContribution(UUIDPKMixin, TimestampMixin, Base):
    """Money moved into (positive) or out of (negative) a savings goal."""

    __tablename__ = "goal_contributions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount_krw: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    contributed_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))

    goal: Mapped["Goal"] = relationship(back_populates="contributions")
