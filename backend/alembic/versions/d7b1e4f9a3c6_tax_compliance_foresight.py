"""tax compliance foresight

Adds the three user-owned tables behind tax & compliance foresight: the
user's tax-year / jurisdiction profile, their per-rule overrides (their own
figure, on/off, and where the figure came from), and receipt annotations on
expenses.

The rules themselves are NOT a table. They live in the git-versioned
app/data/compliance_rules.json, so a rule change is a reviewable diff rather
than an unversioned UPDATE on a production row — see
[[compliance-rules-are-data]] in app/services/compliance_rules.py. Flags are
computed on every read and never stored.

Revision ID: d7b1e4f9a3c6
Revises: e7c1b5a9d3f2
Create Date: 2026-09-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d7b1e4f9a3c6"
down_revision: Union[str, None] = "e7c1b5a9d3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Duplicated on purpose: migrations never import app code.
ASSUMPTION_SOURCE_VALUES = ("unverified_default", "user_set", "user_verified")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    use_checkfirst = not op.get_context().as_sql
    postgresql.ENUM(*ASSUMPTION_SOURCE_VALUES, name="assumption_source").create(op.get_bind(), checkfirst=use_checkfirst)
    assumption_source_ref = postgresql.ENUM(*ASSUMPTION_SOURCE_VALUES, name="assumption_source", create_type=False)

    op.create_table(
        "user_compliance_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("residence_jurisdiction", sa.String(length=2), nullable=True),
        sa.Column("home_jurisdiction", sa.String(length=2), nullable=True),
        sa.Column("fiscal_year_start_month", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("fiscal_year_start_day", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("jurisdiction_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "fiscal_year_start_month BETWEEN 1 AND 12", name=op.f("ck_user_compliance_profiles_fiscal_month_range")
        ),
        sa.CheckConstraint(
            "fiscal_year_start_day BETWEEN 1 AND 31", name=op.f("ck_user_compliance_profiles_fiscal_day_range")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_compliance_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_compliance_profiles")),
    )
    op.create_index(op.f("ix_user_compliance_profiles_user_id"), "user_compliance_profiles", ["user_id"], unique=True)

    op.create_table(
        "compliance_rule_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_key", sa.String(length=64), nullable=False),
        sa.Column("threshold_amount_krw", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("assumption_source", assumption_source_ref, server_default="unverified_default", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_note", sa.String(length=500), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_compliance_rule_overrides_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_compliance_rule_overrides")),
        sa.UniqueConstraint("user_id", "rule_key", name=op.f("uq_compliance_rule_overrides_user_id_rule_key")),
    )
    op.create_index(op.f("ix_compliance_rule_overrides_user_id"), "compliance_rule_overrides", ["user_id"])

    op.create_table(
        "expense_tax_annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expense_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("has_documentation", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("document_ref", sa.String(length=255), nullable=True),
        sa.Column("annotated_on", sa.Date(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_expense_tax_annotations_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["expense_id"], ["expenses.id"], name=op.f("fk_expense_tax_annotations_expense_id_expenses"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expense_tax_annotations")),
    )
    op.create_index(op.f("ix_expense_tax_annotations_user_id"), "expense_tax_annotations", ["user_id"])
    op.create_index(op.f("ix_expense_tax_annotations_expense_id"), "expense_tax_annotations", ["expense_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_expense_tax_annotations_expense_id"), table_name="expense_tax_annotations")
    op.drop_index(op.f("ix_expense_tax_annotations_user_id"), table_name="expense_tax_annotations")
    op.drop_table("expense_tax_annotations")
    op.drop_index(op.f("ix_compliance_rule_overrides_user_id"), table_name="compliance_rule_overrides")
    op.drop_table("compliance_rule_overrides")
    op.drop_index(op.f("ix_user_compliance_profiles_user_id"), table_name="user_compliance_profiles")
    op.drop_table("user_compliance_profiles")
    use_checkfirst = not op.get_context().as_sql
    postgresql.ENUM(name="assumption_source").drop(op.get_bind(), checkfirst=use_checkfirst)
