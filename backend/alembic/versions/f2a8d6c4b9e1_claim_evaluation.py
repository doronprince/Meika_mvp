"""claim evaluation

Adds claim_evaluations (user-owned, one frozen snapshot per evaluation: the
full report as returned, plus the scalar columns the history view and the
daily live-search budget query on) and claim_evidence_cache (shared public
search results keyed by a hash of country + normalized claim, a documented
exemption from tenant isolation like the price catalog: it never stores raw
claim text or anything identifying).

Status-like columns are VARCHAR with CHECK constraints rather than Postgres
enum types: their values live in app/services/claim_sources.py and
app/models/claim.py, and no type objects need creating or dropping.

Revision ID: f2a8d6c4b9e1
Revises: d7b1e4f9a3c6
Create Date: 2026-09-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f2a8d6c4b9e1"
down_revision: Union[str, None] = "d7b1e4f9a3c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Duplicated on purpose: migrations never import app code.
CLAIM_TYPE_VALUES = ("safety_guarantee", "return_prediction", "timing", "superlative", "factual_rate", "unclassified")
EVIDENCE_STATUS_VALUES = ("live", "cached", "live_empty", "quota_exhausted", "unavailable")
EVIDENCE_STANCE_VALUES = (
    "sources_lean_supporting", "sources_lean_disputing", "sources_disagree", "no_directional_language",
    "not_applicable",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "claim_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.String(length=200), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("claim_type", sa.String(length=24), nullable=False),
        sa.Column("evidence_status", sa.String(length=24), nullable=False),
        sa.Column("evidence_stance", sa.String(length=32), nullable=False),
        sa.Column("caution_score", sa.Integer(), nullable=True),
        sa.Column("caution_score_upper", sa.Integer(), nullable=True),
        sa.Column("source_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stake_amount_krw", sa.Numeric(12, 2), nullable=True),
        sa.Column("evidence_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engine_version", sa.String(length=16), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in("claim_type", CLAIM_TYPE_VALUES), name="ck_claim_evaluations_claim_type_values"),
        sa.CheckConstraint(
            _in("evidence_status", EVIDENCE_STATUS_VALUES), name="ck_claim_evaluations_evidence_status_values"
        ),
        sa.CheckConstraint(
            _in("evidence_stance", EVIDENCE_STANCE_VALUES), name="ck_claim_evaluations_evidence_stance_values"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_claim_evaluations_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_claim_evaluations"),
    )
    op.create_index("ix_claim_evaluations_user_id", "claim_evaluations", ["user_id"], unique=False)
    op.create_index("ix_claim_evaluations_query_hash", "claim_evaluations", ["query_hash"], unique=False)

    op.create_table(
        "claim_evidence_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("normalized_query", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_claim_evidence_cache"),
        sa.UniqueConstraint("query_hash", name="uq_claim_evidence_cache_query_hash"),
    )


def downgrade() -> None:
    op.drop_table("claim_evidence_cache")
    op.drop_index("ix_claim_evaluations_query_hash", table_name="claim_evaluations")
    op.drop_index("ix_claim_evaluations_user_id", table_name="claim_evaluations")
    op.drop_table("claim_evaluations")
