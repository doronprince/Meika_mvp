import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.services import fx_service

_CENTS = Decimal("0.01")


class UnsupportedCurrencyError(Exception):
    pass


async def create_expense(db: AsyncSession, user_id: uuid.UUID, data: ExpenseCreate) -> Expense:
    payload = data.model_dump(exclude={"foreign_amount", "foreign_currency"})

    if data.foreign_amount is not None:
        currency = data.foreign_currency.upper()
        if currency not in fx_service.SUPPORTED_CURRENCIES:
            raise UnsupportedCurrencyError(f"{currency} is not a supported currency")
        converted = await fx_service.convert(data.foreign_amount, currency, "KRW")
        payload["amount_krw"] = converted.quantize(_CENTS, rounding=ROUND_HALF_UP)
        payload["original_currency"] = currency
        payload["original_amount"] = data.foreign_amount

    expense = Expense(user_id=user_id, **payload)
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


async def list_expenses(db: AsyncSession, user_id: uuid.UUID) -> list[Expense]:
    result = await db.execute(
        select(Expense).where(Expense.user_id == user_id).order_by(Expense.occurred_on.desc())
    )
    return list(result.scalars().all())


async def get_expense(db: AsyncSession, user_id: uuid.UUID, expense_id: uuid.UUID) -> Expense | None:
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_expense(
    db: AsyncSession, user_id: uuid.UUID, expense_id: uuid.UUID, data: ExpenseUpdate
) -> Expense | None:
    expense = await get_expense(db, user_id, expense_id)
    if expense is None:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)

    await db.commit()
    await db.refresh(expense)
    return expense


async def delete_expense(db: AsyncSession, user_id: uuid.UUID, expense_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    )
    await db.commit()
    return result.rowcount > 0
