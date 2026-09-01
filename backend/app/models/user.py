from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.chat import ChatMessage
    from app.models.expense import Expense

# Default monthly budget threshold (KRW) applied to a new user until they set
# their own. Lives here, once, so the migration's server_default and the ORM
# default can never drift apart.
DEFAULT_MONTHLY_BUDGET_KRW = Decimal("600000.00")

# Every amount is stored in KRW regardless of preferred_currency — this is
# purely a display preference read by GET /fx/rates callers. See
# [[fx-conversion-is-display-only]].
DEFAULT_PREFERRED_CURRENCY = "KRW"


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    monthly_budget_krw: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=DEFAULT_MONTHLY_BUDGET_KRW,
        server_default=str(DEFAULT_MONTHLY_BUDGET_KRW),
        nullable=False,
    )
    # ISO 4217 code (e.g. "USD", "EUR"). Display-only — see
    # [[fx-conversion-is-display-only]] guardrail in app/services/fx_service.py.
    preferred_currency: Mapped[str] = mapped_column(
        String(3),
        default=DEFAULT_PREFERRED_CURRENCY,
        server_default=DEFAULT_PREFERRED_CURRENCY,
        nullable=False,
    )

    expenses: Mapped[list["Expense"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="user", cascade="all, delete-orphan")
