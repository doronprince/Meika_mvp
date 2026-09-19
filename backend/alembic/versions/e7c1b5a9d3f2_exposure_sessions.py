"""exposure sessions

Adds exposure_sessions: screen time the user logs themselves (platform, kind
of content, minutes, day, optional starting hour). This is the only input
the exposure-vs-spending module has beyond the expense ledger: Meika has no
social-media or app-usage API access and the module is designed around that
fact rather than pretending otherwise. The association statistics are
computed on request in app/services/exposure_service.py and never stored.

Revision ID: e7c1b5a9d3f2
Revises: a3d9f6b1c8e4
Create Date: 2026-09-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e7c1b5a9d3f2"
down_revision: Union[str, None] = "a3d9f6b1c8e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Duplicated on purpose: migrations never import app code.
EXPOSURE_KIND_VALUES = ("social_feed", "shopping_app", "influencer_content", "ads_and_deal_alerts", "other")


def upgrade() -> None:
    bind = op.get_bind()
    use_checkfirst = not op.get_context().as_sql
    postgresql.ENUM(*EXPOSURE_KIND_VALUES, name="exposure_kind").create(bind, checkfirst=use_checkfirst)
    exposure_kind_ref = postgresql.ENUM(*EXPOSURE_KIND_VALUES, name="exposure_kind", create_type=False)

    op.create_table(
        "exposure_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("started_hour", sa.SmallInteger(), nullable=True),
        sa.Column("platform", sa.String(length=60), nullable=False),
        sa.Column("kind", exposure_kind_ref, nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("minutes >= 1 AND minutes <= 1440", name="ck_exposure_sessions_minutes_range"),
        sa.CheckConstraint(
            "started_hour IS NULL OR (started_hour >= 0 AND started_hour <= 23)",
            name="ck_exposure_sessions_started_hour_range",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_exposure_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exposure_sessions"),
    )
    op.create_index("ix_exposure_sessions_user_id", "exposure_sessions", ["user_id"], unique=False)
    op.create_index("ix_exposure_sessions_occurred_on", "exposure_sessions", ["occurred_on"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_exposure_sessions_occurred_on", table_name="exposure_sessions")
    op.drop_index("ix_exposure_sessions_user_id", table_name="exposure_sessions")
    op.drop_table("exposure_sessions")

    bind = op.get_bind()
    use_checkfirst = not op.get_context().as_sql
    postgresql.ENUM(name="exposure_kind").drop(bind, checkfirst=use_checkfirst)
