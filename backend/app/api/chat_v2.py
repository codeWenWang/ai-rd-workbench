import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.serializers import serialize
from app.dependencies import AppContainer, get_container


router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ConversationPatch(BaseModel):
    title: str = Field(min_length=1, max_length=300)


@router.post("/api/chat/session")
def create_session(container: AppContainer = Depends(get_container)):
    return {"session_id": container.chat_use_case.create_session().id}


@router.post("/api/chat")
async def chat(request: ChatRequest, container: AppContainer = Depends(get_container)):
    return await container.chat_use_case.chat(request.message, request.session_id)


@router.post("/api/chat/stream")
async def stream_chat(request: ChatRequest, container: AppContainer = Depends(get_container)):
    async def events() -> AsyncIterator[str]:
        yield _event("stage", {"stage": "retrieving"})
        try:
            result = await container.chat_use_case.chat(request.message, request.session_id)
            yield _event("stage", {"stage": "generating"})
            answer = result["answer"]
            for start in range(0, len(answer), 24):
                yield _event("token", {"token": answer[start:start + 24]})
            yield _event("citations", result.get("citations", []))
            for warning in result.get("warnings", []):
                yield _event("warning", {"warning": warning})
            yield _event("done", result)
        except Exception as exc:
            yield _event("error", {"code": getattr(exc, "code", "chat_failed"), "message": str(exc)})
            yield _event("done", {"ok": False})
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _event(name: str, payload) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/api/conversations")
def list_conversations(include_archived: bool = False, offset: int = 0, limit: int = 100,
                       container: AppContainer = Depends(get_container)):
    items = container.conversations.list(include_archived=include_archived, offset=offset, limit=limit)
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/api/conversations/{conversation_id}/messages")
def list_messages(conversation_id: str, container: AppContainer = Depends(get_container)):
    items = container.conversations.list_messages(conversation_id)
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.patch("/api/conversations/{conversation_id}")
def rename_conversation(conversation_id: str, patch: ConversationPatch,
                        container: AppContainer = Depends(get_container)):
    return serialize(container.conversations.rename(conversation_id, patch.title))


@router.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, container: AppContainer = Depends(get_container)):
    container.conversations.delete(conversation_id)
    return {"success": True}


@router.get("/api/chat/history/{session_id}")
def legacy_history(session_id: str, container: AppContainer = Depends(get_container)):
    return {"messages": [serialize(item) for item in container.conversations.list_messages(session_id)]}


@router.delete("/api/chat/history/{session_id}")
def legacy_clear_history(session_id: str, container: AppContainer = Depends(get_container)):
    container.conversations.delete(session_id)
    return {"success": True, "message": "Conversation history cleared"}
