import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ExposureKind, enum_values

if TYPE_CHECKING:
    from app.models.user import User


class ExposureSession(UUIDPKMixin, TimestampMixin, Base):
    """A stretch of screen time the user logged themselves: minutes on a
    feed, a shopping app, influencer content or deal alerts. Meika has no
    access to social-media or app-usage APIs and never pretends to; every
    row here was typed in (or imported) by the user. Always scoped by
    user_id (see [[tenant-isolation]])."""

    __tablename__ = "exposure_sessions"
    __table_args__ = (
        CheckConstraint("minutes >= 1 AND minutes <= 1440", name="minutes_range"),
        CheckConstraint("started_hour IS NULL OR (started_hour >= 0 AND started_hour <= 23)", name="started_hour_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    started_hour: Mapped[int | None] = mapped_column(SmallInteger)
    platform: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[ExposureKind] = mapped_column(
        SAEnum(ExposureKind, name="exposure_kind", values_callable=enum_values),
        nullable=False,
    )
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="exposure_sessions")
