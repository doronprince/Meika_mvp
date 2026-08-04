import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ExpenseCategory, StoreType, TransitMode, enum_values

if TYPE_CHECKING:
    pass

# Seoul retail catalog: shared reference data, not tenant-owned. Every user
# reads the same Store/Product/PriceQuote rows — no user_id on these tables.


class Store(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "stores"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    store_type: Mapped[StoreType] = mapped_column(
        SAEnum(StoreType, name="store_type", values_callable=enum_values), nullable=False
    )
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    default_transit_mode: Mapped[TransitMode] = mapped_column(
        SAEnum(TransitMode, name="transit_mode", values_callable=enum_values),
        default=TransitMode.WALK,
        server_default=TransitMode.WALK.value,
        nullable=False,
    )
    default_transit_cost_krw: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), default=Decimal("4.5"), server_default="4.5", nullable=False)

    listings: Mapped[list["ProductListing"]] = relationship(back_populates="store", cascade="all, delete-orphan")


class Product(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[ExpenseCategory] = mapped_column(
        SAEnum(ExpenseCategory, name="expense_category", values_callable=enum_values), nullable=False
    )

    listings: Mapped[list["ProductListing"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductListing(UUIDPKMixin, TimestampMixin, Base):
    """A store's current offer for a product — the fast-lookup row Phase 3's
    price comparison reads. Historical price movement lives in PriceQuote;
    trend (rising/falling/stable) is computed from that history, never
    stored as a hardcoded label."""

    __tablename__ = "product_listings"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )

    price_krw: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    product: Mapped["Product"] = relationship(back_populates="listings")
    store: Mapped["Store"] = relationship(back_populates="listings")
    price_history: Mapped[list["PriceQuote"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan", order_by="PriceQuote.observed_at"
    )


class PriceQuote(UUIDPKMixin, Base):
    """Immutable price observation. Append-only — never updated in place —
    so Phase 3 can derive a real price trend from consecutive observations."""

    __tablename__ = "price_quotes"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price_krw: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    listing: Mapped["ProductListing"] = relationship(back_populates="price_history")
