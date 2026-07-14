from fastapi import APIRouter, File, Form, UploadFile

from app.models.schemas import MemoryResponse, TextMemoryRequest
from app.services.long_term_memory import long_term_memory

router = APIRouter(prefix="/api/memory", tags=["long-term-memory"])


@router.post("/text", response_model=MemoryResponse)
def add_text_memory(req: TextMemoryRequest):
    result = long_term_memory.ingest_text(req.session_id, req.text, req.title)
    return MemoryResponse(**result)


@router.post("/pdf", response_model=MemoryResponse)
async def add_pdf_memory(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    content = await file.read()
    result = long_term_memory.ingest_pdf(session_id, content, file.filename or "upload.pdf")
    return MemoryResponse(**result)


@router.post("/recall")
def recall_memory(session_id: str = Form(...), query: str = Form(...)):
    context = long_term_memory.recall(session_id, query)
    return {"context": context, "found": bool(context)}
