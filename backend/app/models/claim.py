import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin

# Stored as VARCHAR + CHECK rather than Postgres enum types: the values are
# owned by app/services/claim_sources.py and schemas/claim.py, and this keeps
# the migration free of type objects that would need creating and dropping.
CLAIM_TYPE_VALUES = ("safety_guarantee", "return_prediction", "timing", "superlative", "factual_rate", "unclassified")
EVIDENCE_STATUS_VALUES = ("live", "cached", "live_empty", "quota_exhausted", "unavailable")
EVIDENCE_STANCE_VALUES = (
    "sources_lean_supporting", "sources_lean_disputing", "sources_disagree", "no_directional_language",
    "not_applicable",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class ClaimEvaluation(UUIDPKMixin, TimestampMixin, Base):
    """One evaluation of a claim, frozen at the time it ran. Search results
    change by the day and by country, so an evaluation is only auditable if
    the evidence and the user's numbers that produced it are stored with it:
    `report` holds the full response exactly as returned, and nothing here is
    ever recomputed on read. Always scoped by user_id ([[tenant-isolation]])."""

    __tablename__ = "claim_evaluations"
    __table_args__ = (
        CheckConstraint(_in("claim_type", CLAIM_TYPE_VALUES), name="claim_type_values"),
        CheckConstraint(_in("evidence_status", EVIDENCE_STATUS_VALUES), name="evidence_status_values"),
        CheckConstraint(_in("evidence_stance", EVIDENCE_STANCE_VALUES), name="evidence_stance_values"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(String(200), nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(24), nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(24), nullable=False)
    evidence_stance: Mapped[str] = mapped_column(String(32), nullable=False)
    caution_score: Mapped[int | None] = mapped_column(Integer)
    caution_score_upper: Mapped[int | None] = mapped_column(Integer)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stake_amount_krw: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    evidence_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    engine_version: Mapped[str] = mapped_column(String(16), nullable=False)
    report: Mapped[dict] = mapped_column(JSONB, nullable=False)


class ClaimEvidenceCache(UUIDPKMixin, TimestampMixin, Base):
    """Shared search results keyed by a hash of country + normalized claim.
    A documented exemption from [[tenant-isolation]], like the price catalog:
    it holds only public search results for a derived search string, never
    raw claim text or anything that identifies who asked."""

    __tablename__ = "claim_evidence_cache"

    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    normalized_query: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    results: Mapped[list] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
