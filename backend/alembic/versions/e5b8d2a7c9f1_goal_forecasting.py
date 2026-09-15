"""goal forecasting

Adds savings goals / spending caps and the contributions that fund savings
goals. The forecast itself (verdict, projection, counterfactual) is computed
on read in app/services/goal_forecast.py and never stored, so there is no
column here that can go stale as expenses are logged.

Revision ID: e5b8d2a7c9f1
Revises: c2e9a7f4d1b8
Create Date: 2026-09-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5b8d2a7c9f1"
down_revision: Union[str, None] = "c2e9a7f4d1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Duplicated on purpose: migrations never import app code, so a later edit to
# app/models/enums.py can't silently rewrite history.
GOAL_TYPE_VALUES = ("savings", "spending_cap")
EXPENSE_CATEGORY_VALUES = (
    "groceries",
    "cafes_and_dining",
    "transportation",
    "housing_and_utilities",
    "education",
    "apparel",
    "electronics",
    "other",
)


def upgrade() -> None:
    # Same recipe as the initial schema: create the ENUM type once, then
    # reference it with create_type=False from the column.
    use_checkfirst = not op.get_context().as_sql
    postgresql.ENUM(*GOAL_TYPE_VALUES, name="goal_type").create(op.get_bind(), checkfirst=use_checkfirst)
    goal_type_ref = postgresql.ENUM(*GOAL_TYPE_VALUES, name="goal_type", create_type=False)
    expense_category_ref = postgresql.ENUM(*EXPENSE_CATEGORY_VALUES, name="expense_category", create_type=False)

    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("goal_type", goal_type_ref, nullable=False),
        sa.Column("target_amount_krw", sa.Numeric(12, 2), nullable=False),
        sa.Column("starting_amount_krw", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("category", expense_category_ref, nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("target_amount_krw > 0", name=op.f("ck_goals_target_positive")),
        sa.CheckConstraint("starting_amount_krw >= 0", name=op.f("ck_goals_starting_non_negative")),
        sa.CheckConstraint("target_date >= start_date", name=op.f("ck_goals_dates_ordered")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_goals_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goals")),
    )
    op.create_index(op.f("ix_goals_user_id"), "goals", ["user_id"])

    op.create_table(
        "goal_contributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_krw", sa.Numeric(12, 2), nullable=False),
        sa.Column("contributed_on", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_goal_contributions_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["goals.id"], name=op.f("fk_goal_contributions_goal_id_goals"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal_contributions")),
    )
    op.create_index(op.f("ix_goal_contributions_user_id"), "goal_contributions", ["user_id"])
    op.create_index(op.f("ix_goal_contributions_goal_id"), "goal_contributions", ["goal_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_goal_contributions_goal_id"), table_name="goal_contributions")
    op.drop_index(op.f("ix_goal_contributions_user_id"), table_name="goal_contributions")
    op.drop_table("goal_contributions")
    op.drop_index(op.f("ix_goals_user_id"), table_name="goals")
    op.drop_table("goals")
    use_checkfirst = not op.get_context().as_sql
    postgresql.ENUM(name="goal_type").drop(op.get_bind(), checkfirst=use_checkfirst)
