"""drop redundant transit columns on product_listings

Transit cost/mode is a property of the store (how far it is to get there),
not of a specific product offered there. product_listings.transit_cost_krw
and .transit_mode had no reachable "unset" state (NOT NULL, default 0/walk)
to fall back to stores.default_transit_cost_krw/default_transit_mode, so
they could only drift from the store's real value, never add information.
Price-Finder (Phase 3) reads transit cost from the store exclusively.

Revision ID: b7d4e8f1a2c3
Revises: f3a9c1d2b6e0
Create Date: 2026-08-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7d4e8f1a2c3"
down_revision: Union[str, None] = "f3a9c1d2b6e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("product_listings", "transit_mode")
    op.drop_column("product_listings", "transit_cost_krw")


def downgrade() -> None:
    # transit_mode is still in active use by expenses.transit_mode and
    # stores.default_transit_mode — re-add the column against the existing
    # type (create_type=False) rather than recreating the type itself.
    transit_mode_ref = postgresql.ENUM(name="transit_mode", create_type=False)

    op.add_column(
        "product_listings",
        sa.Column("transit_cost_krw", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "product_listings",
        sa.Column(
            "transit_mode",
            transit_mode_ref,
            nullable=False,
            server_default=sa.text("'walk'::transit_mode"),
        ),
    )
