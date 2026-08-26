import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import copilot_service
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models.enums import ChatRole
from app.schemas.chat import ChatMessageRead
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/copilot")
async def copilot_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> None:
    """One connection per chat session. A browser WebSocket handshake can't
    carry the REST routes' Authorization header, so the same JWT travels as
    a query param instead — see [[api/deps.py]] guardrail note."""
    try:
        user_id = decode_access_token(token)
    except InvalidTokenError:
        await websocket.close(code=4401, reason="Invalid or expired token")
        return

    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            content = str(payload.get("content", "")).strip()
            if not content:
                continue

            await chat_service.add_message(db, user_id, ChatRole.USER, content)
            try:
                reply_text, factors = await copilot_service.generate_reply(db, user_id, content)
            except Exception:
                logger.exception("Copilot reply generation failed")
                await websocket.send_json({"type": "error", "detail": "The Wise Guide couldn't respond — try again."})
                continue

            assistant_message = await chat_service.add_message(db, user_id, ChatRole.ASSISTANT, reply_text, factors)
            await websocket.send_json(
                {
                    "type": "message",
                    "message": ChatMessageRead.model_validate(assistant_message).model_dump(mode="json"),
                }
            )
    except WebSocketDisconnect:
        pass
