import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ChatRole, enum_values

if TYPE_CHECKING:
    from app.models.user import User


class ChatMessage(UUIDPKMixin, TimestampMixin, Base):
    """A single turn in the Wise Guide conversation. xai_factors is a
    structured JSON array of the concrete factors behind a reply — populated
    only for assistant turns that carry a recommendation, never a fabricated
    string (see [[xai-enforcement]] guardrail)."""

    __tablename__ = "chat_messages"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[ChatRole] = mapped_column(
        SAEnum(ChatRole, name="chat_role", values_callable=enum_values), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    xai_factors: Mapped[list | None] = mapped_column(JSONB)

    user: Mapped["User"] = relationship(back_populates="chat_messages")
