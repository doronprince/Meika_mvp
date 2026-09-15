import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import IncomeKind, enum_values

if TYPE_CHECKING:
    from app.models.user import User


class IncomeStream(UUIDPKMixin, TimestampMixin, Base):
    """A recurring monthly inflow. Always scoped by user_id (see
    [[tenant-isolation]] guardrail).

    Unlike expenses, the canonical amount here is in the currency the income
    is actually paid in: a family allowance sent in INR is an INR amount, and
    its KRW value genuinely moves with the exchange rate — that movement is
    what the survival module's currency-devaluation shock models.
    monthly_amount_krw_snapshot is the KRW value at the rate live when the
    row was last written, used only as a fallback when live FX is down.
    """

    __tablename__ = "income_streams"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[IncomeKind] = mapped_column(
        SAEnum(IncomeKind, name="income_kind", values_callable=enum_values),
        nullable=False,
    )
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    monthly_amount_krw_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    user: Mapped["User"] = relationship(back_populates="income_streams")
