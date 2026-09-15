import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IncomeKind


class IncomeStreamCreate(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    kind: IncomeKind
    # In the currency the income is actually paid in — see IncomeStream's
    # docstring for why this isn't converted to KRW up front.
    monthly_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="KRW", min_length=3, max_length=3)
    is_active: bool = True


class IncomeStreamUpdate(BaseModel):
    """Partial update, same rule as ExpenseUpdate: NOT NULL fields are typed
    without `| None`, so an omitted key is a no-op but an explicit null is
    rejected instead of nulling a required column."""

    label: str = Field(default=None, min_length=1, max_length=255)
    kind: IncomeKind = None
    monthly_amount: Decimal = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default=None, min_length=3, max_length=3)
    is_active: bool = None


class IncomeStreamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    kind: IncomeKind
    monthly_amount: Decimal
    currency: str
    monthly_amount_krw_snapshot: Decimal
    is_active: bool
    created_at: datetime
