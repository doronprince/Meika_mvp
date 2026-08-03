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

    expenses: Mapped[list["Expense"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="user", cascade="all, delete-orphan")
