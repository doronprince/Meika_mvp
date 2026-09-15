import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.income import IncomeStream
from app.schemas.income import IncomeStreamCreate, IncomeStreamUpdate
from app.services import fx_service

_CENTS = Decimal("0.01")


class UnsupportedCurrencyError(Exception):
    pass


async def _krw_snapshot(amount: Decimal, currency: str) -> Decimal:
    if currency == "KRW":
        return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)
    converted = await fx_service.convert(amount, currency, "KRW")
    return converted.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _normalize_currency(currency: str) -> str:
    code = currency.upper()
    if code not in fx_service.SUPPORTED_CURRENCIES:
        raise UnsupportedCurrencyError(f"{code} is not a supported currency")
    return code


async def create_income_stream(db: AsyncSession, user_id: uuid.UUID, data: IncomeStreamCreate) -> IncomeStream:
    currency = _normalize_currency(data.currency)
    stream = IncomeStream(
        user_id=user_id,
        label=data.label,
        kind=data.kind,
        monthly_amount=data.monthly_amount,
        currency=currency,
        monthly_amount_krw_snapshot=await _krw_snapshot(data.monthly_amount, currency),
        is_active=data.is_active,
    )
    db.add(stream)
    await db.commit()
    await db.refresh(stream)
    return stream


async def list_income_streams(db: AsyncSession, user_id: uuid.UUID) -> list[IncomeStream]:
    result = await db.execute(
        select(IncomeStream).where(IncomeStream.user_id == user_id).order_by(IncomeStream.created_at)
    )
    return list(result.scalars().all())


async def get_income_stream(db: AsyncSession, user_id: uuid.UUID, stream_id: uuid.UUID) -> IncomeStream | None:
    result = await db.execute(
        select(IncomeStream).where(IncomeStream.id == stream_id, IncomeStream.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_income_stream(
    db: AsyncSession, user_id: uuid.UUID, stream_id: uuid.UUID, data: IncomeStreamUpdate
) -> IncomeStream | None:
    stream = await get_income_stream(db, user_id, stream_id)
    if stream is None:
        return None

    updates = data.model_dump(exclude_unset=True)
    if "currency" in updates:
        updates["currency"] = _normalize_currency(updates["currency"])
    for field, value in updates.items():
        setattr(stream, field, value)

    if "currency" in updates or "monthly_amount" in updates:
        stream.monthly_amount_krw_snapshot = await _krw_snapshot(stream.monthly_amount, stream.currency)

    await db.commit()
    await db.refresh(stream)
    return stream


async def delete_income_stream(db: AsyncSession, user_id: uuid.UUID, stream_id: uuid.UUID) -> bool:
    result = await db.execute(
        delete(IncomeStream).where(IncomeStream.id == stream_id, IncomeStream.user_id == user_id)
    )
    await db.commit()
    return result.rowcount > 0
