import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.models.enums import ExpenseCategory, TransitMode


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: ExpenseCategory
    amount_krw: Decimal | None = Field(default=None, gt=0)
    # Alternative to amount_krw: log the expense in the currency you actually
    # paid in. The backend converts to KRW via a live rate at creation time
    # and stores both the KRW result and this original figure — see
    # [[fx-conversion-is-display-only]] in app/services/fx_service.py.
    foreign_amount: Decimal | None = Field(default=None, gt=0)
    foreign_currency: str | None = Field(default=None, min_length=3, max_length=3)
    store_name: str | None = Field(default=None, max_length=255)
    transit_cost_krw: Decimal = Field(default=Decimal("0"), ge=0)
    transit_mode: TransitMode = TransitMode.WALK
    occurred_on: date
    notes: str | None = None

    @model_validator(mode="after")
    def _exactly_one_amount_source(self):
        has_foreign_amount = self.foreign_amount is not None
        has_foreign_currency = self.foreign_currency is not None
        if has_foreign_amount != has_foreign_currency:
            raise ValueError("foreign_amount and foreign_currency must be provided together")

        has_krw = self.amount_krw is not None
        has_foreign = has_foreign_amount and has_foreign_currency
        if has_krw == has_foreign:
            raise ValueError("Provide either amount_krw or (foreign_amount + foreign_currency), not both or neither")
        return self


class ExpenseUpdate(BaseModel):
    """Partial update. Fields that are NOT NULL on the model (everything but
    store_name/notes) are typed without `| None`: omitting a key is a no-op
    (filtered by exclude_unset in the service layer), but an explicit
    `"field": null` fails validation instead of silently nulling a required
    column."""

    title: str = Field(default=None, min_length=1, max_length=255)
    category: ExpenseCategory = None
    amount_krw: Decimal = Field(default=None, gt=0)
    store_name: str | None = Field(default=None, max_length=255)
    transit_cost_krw: Decimal = Field(default=None, ge=0)
    transit_mode: TransitMode = None
    occurred_on: date = None
    notes: str | None = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    category: ExpenseCategory
    amount_krw: Decimal
    store_name: str | None
    transit_cost_krw: Decimal
    transit_mode: TransitMode
    occurred_on: date
    notes: str | None
    created_at: datetime
    original_currency: str | None
    original_amount: Decimal | None

    @computed_field
    @property
    def total_economic_cost_krw(self) -> Decimal:
        return self.amount_krw + self.transit_cost_krw
