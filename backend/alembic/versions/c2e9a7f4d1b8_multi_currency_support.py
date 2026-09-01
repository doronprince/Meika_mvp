"""multi-currency support

Adds users.preferred_currency (a display-only ISO 4217 code read by
GET /fx/rates callers -- every stored amount stays in KRW, see
[[fx-conversion-is-display-only]] in app/services/fx_service.py) and two
nullable columns on expenses for capturing a foreign-currency entry:
original_currency + original_amount. amount_krw remains the canonical,
always-populated field -- these two are only an audit trail of what was
actually paid and the live rate used to convert it, so a past expense's KRW
value never drifts as rates move later.

Revision ID: c2e9a7f4d1b8
Revises: b7d4e8f1a2c3
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2e9a7f4d1b8"
down_revision: Union[str, None] = "b7d4e8f1a2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferred_currency", sa.String(length=3), nullable=False, server_default="KRW"),
    )
    op.add_column("expenses", sa.Column("original_currency", sa.String(length=3), nullable=True))
    op.add_column("expenses", sa.Column("original_amount", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("expenses", "original_amount")
    op.drop_column("expenses", "original_currency")
    op.drop_column("users", "preferred_currency")
