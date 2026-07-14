from fastapi import APIRouter, File, Form, UploadFile

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    KnowledgeTextRequest,
    MemoryResponse,
    SessionResponse,
    TextMemoryRequest,
)
from app.services.chat_service import chat_service
from app.services.long_term_memory import long_term_memory
from app.services.rag_service import rag_service
from app.services.short_term_memory import short_term_memory

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/session", response_model=SessionResponse)
def create_session():
    return SessionResponse(session_id=short_term_memory.create_session())


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or short_term_memory.create_session()
    result = chat_service.chat(session_id, req.message)
    return ChatResponse(**result)


@router.get("/history/{session_id}")
def get_history(session_id: str):
    return {"messages": short_term_memory.get_recent_messages(session_id)}


@router.delete("/history/{session_id}")
def clear_history(session_id: str):
    short_term_memory.clear(session_id)
    return {"success": True, "message": "会话历史已清除"}
