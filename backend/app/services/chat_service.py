import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage
from app.models.enums import ChatRole
from app.schemas.common import XAIFactor


async def list_messages(db: AsyncSession, user_id: uuid.UUID, limit: int = 50) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def add_message(
    db: AsyncSession,
    user_id: uuid.UUID,
    role: ChatRole,
    content: str,
    xai_factors: list[XAIFactor] | None = None,
) -> ChatMessage:
    message = ChatMessage(
        user_id=user_id,
        role=role,
        content=content,
        xai_factors=[factor.model_dump() for factor in xai_factors] if xai_factors else None,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
