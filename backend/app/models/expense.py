import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ExpenseCategory, TransitMode, enum_values

if TYPE_CHECKING:
    from app.models.user import User


class Expense(UUIDPKMixin, TimestampMixin, Base):
    """A user-owned transaction. Always scoped by user_id — never queried
    without it (see [[tenant-isolation]] guardrail)."""

    __tablename__ = "expenses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[ExpenseCategory] = mapped_column(
        SAEnum(
            ExpenseCategory,
            name="expense_category",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    amount_krw: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    store_name: Mapped[str | None] = mapped_column(String(255))
    transit_cost_krw: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0", nullable=False)
    transit_mode: Mapped[TransitMode] = mapped_column(
        SAEnum(
            TransitMode,
            name="transit_mode",
            values_callable=enum_values,
        ),
        default=TransitMode.WALK,
        server_default=TransitMode.WALK.value,
        nullable=False,
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="expenses")
