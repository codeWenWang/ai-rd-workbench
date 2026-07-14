from fastapi import APIRouter, File, Form, UploadFile

from app.models.schemas import KnowledgeTextRequest, MemoryResponse
from app.services.rag_service import rag_service

router = APIRouter(prefix="/api/knowledge", tags=["knowledge-base"])


@router.post("/text", response_model=MemoryResponse)
def add_knowledge_text(req: KnowledgeTextRequest):
    result = rag_service.ingest_text(req.text, req.title, req.category)
    return MemoryResponse(**result)


@router.post("/pdf", response_model=MemoryResponse)
async def add_knowledge_pdf(
    file: UploadFile = File(...),
    category: str = Form("general"),
):
    content = await file.read()
    result = rag_service.ingest_pdf(content, file.filename or "upload.pdf", category)
    return MemoryResponse(**result)
