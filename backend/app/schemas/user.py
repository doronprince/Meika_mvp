import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    monthly_budget_krw: Decimal
    preferred_currency: str


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    monthly_budget_krw: Decimal | None = Field(default=None, gt=0)
    preferred_currency: str | None = Field(default=None, min_length=3, max_length=3)
