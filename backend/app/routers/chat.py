import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.chat import ChatMessageRead
from app.services import chat_service

router = APIRouter(prefix="/copilot", tags=["Copilot"])


@router.get("/history", response_model=list[ChatMessageRead])
async def get_chat_history(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ChatMessageRead]:
    messages = await chat_service.list_messages(db, user_id)
    return [ChatMessageRead.model_validate(message) for message in messages]
