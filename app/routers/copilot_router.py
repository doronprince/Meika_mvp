from fastapi import APIRouter
from app.services.xai_copilot import process_copilot_chat
from app.models import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/copilot", tags=["XAI Copilot"])

@router.post("/chat", response_model=ChatResponse)
def chat_with_copilot(request: ChatRequest):
    return process_copilot_chat(request.message)
