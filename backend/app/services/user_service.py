import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserUpdate
from app.services import fx_service


class UnsupportedCurrencyError(Exception):
    pass


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def update_user(db: AsyncSession, user_id: uuid.UUID, data: UserUpdate) -> User | None:
    user = await db.get(User, user_id)
    if user is None:
        return None

    updates = data.model_dump(exclude_unset=True)
    if "preferred_currency" in updates:
        currency = updates["preferred_currency"].upper()
        if currency not in fx_service.SUPPORTED_CURRENCIES:
            raise UnsupportedCurrencyError(f"{currency} is not a supported currency")
        updates["preferred_currency"] = currency

    for field, value in updates.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user
