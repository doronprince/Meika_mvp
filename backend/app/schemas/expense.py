import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import ExpenseCategory, TransitMode


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: ExpenseCategory
    amount_krw: Decimal = Field(gt=0)
    store_name: str | None = Field(default=None, max_length=255)
    transit_cost_krw: Decimal = Field(default=Decimal("0"), ge=0)
    transit_mode: TransitMode = TransitMode.WALK
    occurred_on: date
    notes: str | None = None


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

    @computed_field
    @property
    def total_economic_cost_krw(self) -> Decimal:
        return self.amount_krw + self.transit_cost_krw
