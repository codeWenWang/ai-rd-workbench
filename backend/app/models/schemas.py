from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: dict


class TextMemoryRequest(BaseModel):
    session_id: str
    text: str = Field(..., min_length=1)
    title: str = ""


class MemoryResponse(BaseModel):
    success: bool
    message: str
    count: int = 0


class SessionResponse(BaseModel):
    session_id: str


class KnowledgeTextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    title: str = ""
    category: str = "general"
