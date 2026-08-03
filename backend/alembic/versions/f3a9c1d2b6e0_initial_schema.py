"""initial schema

Revision ID: f3a9c1d2b6e0
Revises:
Create Date: 2026-08-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3a9c1d2b6e0"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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
TRANSIT_MODE_VALUES = ("walk", "subway_bus", "taxi")
STORE_TYPE_VALUES = ("online", "local_supermarket", "traditional_market", "convenience_store")
CHAT_ROLE_VALUES = ("user", "assistant")


def upgrade() -> None:
    bind = op.get_bind()

    # Postgres ENUM types are created once, explicitly, then referenced with
    # create_type=False on every column that uses them — otherwise the second
    # create_table referencing the same type fails with "type already exists".
    expense_category = postgresql.ENUM(*EXPENSE_CATEGORY_VALUES, name="expense_category")
    transit_mode = postgresql.ENUM(*TRANSIT_MODE_VALUES, name="transit_mode")
    store_type = postgresql.ENUM(*STORE_TYPE_VALUES, name="store_type")
    chat_role = postgresql.ENUM(*CHAT_ROLE_VALUES, name="chat_role")

    expense_category.create(bind, checkfirst=True)
    transit_mode.create(bind, checkfirst=True)
    store_type.create(bind, checkfirst=True)
    chat_role.create(bind, checkfirst=True)

    expense_category_ref = postgresql.ENUM(*EXPENSE_CATEGORY_VALUES, name="expense_category", create_type=False)
    transit_mode_ref = postgresql.ENUM(*TRANSIT_MODE_VALUES, name="transit_mode", create_type=False)
    store_type_ref = postgresql.ENUM(*STORE_TYPE_VALUES, name="store_type", create_type=False)
    chat_role_ref = postgresql.ENUM(*CHAT_ROLE_VALUES, name="chat_role", create_type=False)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("monthly_budget_krw", sa.Numeric(12, 2), nullable=False, server_default=sa.text("600000.00")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", expense_category_ref, nullable=False),
        sa.Column("amount_krw", sa.Numeric(12, 2), nullable=False),
        sa.Column("store_name", sa.String(255), nullable=True),
        sa.Column("transit_cost_krw", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "transit_mode",
            transit_mode_ref,
            nullable=False,
            server_default=sa.text("'walk'::transit_mode"),
        ),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_expenses_user_id", "expenses", ["user_id"])
    op.create_index("ix_expenses_occurred_on", "expenses", ["occurred_on"])

    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("store_type", store_type_ref, nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column(
            "default_transit_mode",
            transit_mode_ref,
            nullable=False,
            server_default=sa.text("'walk'::transit_mode"),
        ),
        sa.Column("default_transit_cost_krw", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("rating", sa.Numeric(2, 1), nullable=False, server_default=sa.text("4.5")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", expense_category_ref, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_products_name", "products", ["name"])

    op.create_table(
        "product_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price_krw", sa.Numeric(12, 2), nullable=False),
        sa.Column("transit_cost_krw", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "transit_mode",
            transit_mode_ref,
            nullable=False,
            server_default=sa.text("'walk'::transit_mode"),
        ),
        sa.Column("in_stock", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_product_listings_product_id", "product_listings", ["product_id"])
    op.create_index("ix_product_listings_store_id", "product_listings", ["store_id"])

    op.create_table(
        "price_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price_krw", sa.Numeric(12, 2), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_price_quotes_listing_id", "price_quotes", ["listing_id"])
    op.create_index("ix_price_quotes_observed_at", "price_quotes", ["observed_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", chat_role_ref, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("xai_factors", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("price_quotes")
    op.drop_table("product_listings")
    op.drop_table("products")
    op.drop_table("stores")
    op.drop_table("expenses")
    op.drop_table("users")

    bind = op.get_bind()
    postgresql.ENUM(name="chat_role").drop(bind, checkfirst=True)
    postgresql.ENUM(name="store_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="transit_mode").drop(bind, checkfirst=True)
    postgresql.ENUM(name="expense_category").drop(bind, checkfirst=True)
