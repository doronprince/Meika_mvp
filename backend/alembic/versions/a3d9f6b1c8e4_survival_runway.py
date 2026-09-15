"""survival runway

Adds what a financial-survival estimate needs that the expense ledger alone
cannot supply: how much liquid savings the user holds
(users.liquid_savings_krw -- nullable, because NULL means "not told us",
which is materially different from 0) and the recurring monthly income
streams that offset spending (income_streams). The runway itself --
baseline, shocked, per-shock Shapley attribution -- is computed on request
in app/services/survival_service.py and never stored: a stored runway would
go stale the moment an expense is logged.

income_streams.monthly_amount/currency are canonical, not a KRW figure: an
allowance paid in INR really is an INR amount whose KRW value moves with FX,
and that movement is exactly what the currency-devaluation shock models.
monthly_amount_krw_snapshot is only a fallback for when live FX is down --
see [[fx-conversion-is-display-only]] for why every other table stores KRW.

Revision ID: a3d9f6b1c8e4
Revises: e5b8d2a7c9f1
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3d9f6b1c8e4"
down_revision: Union[str, None] = "e5b8d2a7c9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Duplicated on purpose: migrations never import app code, so a later edit to
# app/models/enums.py can't silently rewrite history.
INCOME_KIND_VALUES = ("salary", "part_time", "freelance", "scholarship", "family_support", "other")


def upgrade() -> None:
    bind = op.get_bind()
    # Same offline-mode guard as f3a9c1d2b6e0: checkfirst needs a live
    # connection, which `alembic upgrade --sql` doesn't have.
    use_checkfirst = not op.get_context().as_sql
    postgresql.ENUM(*INCOME_KIND_VALUES, name="income_kind").create(bind, checkfirst=use_checkfirst)
    income_kind_ref = postgresql.ENUM(*INCOME_KIND_VALUES, name="income_kind", create_type=False)

    op.add_column("users", sa.Column("liquid_savings_krw", sa.Numeric(12, 2), nullable=True))

    op.create_table(
        "income_streams",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("kind", income_kind_ref, nullable=False),
        sa.Column("monthly_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("monthly_amount_krw_snapshot", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_income_streams_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_income_streams"),
    )
    op.create_index("ix_income_streams_user_id", "income_streams", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_income_streams_user_id", table_name="income_streams")
    op.drop_table("income_streams")
    op.drop_column("users", "liquid_savings_krw")

    bind = op.get_bind()
    use_checkfirst = not op.get_context().as_sql
    postgresql.ENUM(name="income_kind").drop(bind, checkfirst=use_checkfirst)
