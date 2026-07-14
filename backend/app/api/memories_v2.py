from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.api.serializers import serialize
from app.dependencies import AppContainer, get_container
from app.domain.entities import CandidateStatus, MemoryKind, ResourceType


router = APIRouter(tags=["memories"])


class MemoryRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str = ""
    kind: MemoryKind = MemoryKind.CONTEXT
    session_id: str | None = None


class MemoryPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    content: str | None = Field(default=None, min_length=1)
    kind: MemoryKind | None = None


class CandidatePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    content: str | None = Field(default=None, min_length=1)
    kind: MemoryKind | None = None


@router.get("/api/memories")
def list_memories(include_archived: bool = False, offset: int = 0, limit: int = 100,
                  container: AppContainer = Depends(get_container)):
    items = container.memory_use_case.list(include_archived=include_archived, offset=offset, limit=limit)
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/api/memories/{memory_id}")
def get_memory(memory_id: str, container: AppContainer = Depends(get_container)):
    memory = container.memories.get(memory_id)
    if memory is None:
        from app.domain.errors import ResourceNotFound
        raise ResourceNotFound("memory not found")
    result = serialize(memory)
    result["chunks"] = [serialize(item) for item in container.memories.list_chunks(memory_id)]
    return result


@router.post("/api/memories")
@router.post("/api/memory/text")
async def add_memory(request: MemoryRequest, container: AppContainer = Depends(get_container)):
    memory = await container.memory_use_case.create_text(request.text, title=request.title, kind=request.kind,
                                                         source_conversation_id=request.session_id)
    return {"success": True, "message": "Memory indexed", "count": len(container.memories.list_chunks(memory.id)),
            "memory": serialize(memory), "memory_id": memory.id}


@router.post("/api/memory/pdf")
@router.post("/api/memories/pdf")
async def add_memory_pdf(file: UploadFile = File(...), session_id: str | None = Form(None),
                         kind: MemoryKind = Form(MemoryKind.CONTEXT),
                         container: AppContainer = Depends(get_container)):
    memory = await container.memory_use_case.create_pdf(await file.read(), filename=file.filename or "upload.pdf",
                                                        kind=kind, source_conversation_id=session_id)
    return {"success": True, "message": "Memory indexed", "count": len(container.memories.list_chunks(memory.id)),
            "memory": serialize(memory), "memory_id": memory.id}


@router.patch("/api/memories/{memory_id}")
async def update_memory(memory_id: str, patch: MemoryPatch,
                        container: AppContainer = Depends(get_container)):
    return serialize(await container.memory_use_case.update(memory_id, **patch.model_dump(exclude_unset=True)))


@router.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str, container: AppContainer = Depends(get_container)):
    await container.memory_use_case.delete(memory_id)
    return {"success": True}


@router.get("/api/memory-candidates")
def list_candidates(status: CandidateStatus | None = None, offset: int = 0, limit: int = 100,
                    container: AppContainer = Depends(get_container)):
    items = container.memory_use_case.list_candidates(status=status, offset=offset, limit=limit)
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.patch("/api/memory-candidates/{candidate_id}")
def update_candidate(candidate_id: str, patch: CandidatePatch,
                     container: AppContainer = Depends(get_container)):
    return serialize(container.memory_use_case.update_candidate(candidate_id, **patch.model_dump(exclude_unset=True)))


@router.post("/api/memory-candidates/{candidate_id}/confirm")
async def confirm_candidate(candidate_id: str, container: AppContainer = Depends(get_container)):
    return serialize(await container.memory_use_case.confirm_candidate(candidate_id))


@router.post("/api/memory-candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str, container: AppContainer = Depends(get_container)):
    return serialize(container.memory_use_case.reject_candidate(candidate_id))


@router.post("/api/memory/recall")
async def legacy_recall(query: str = Form(...), session_id: str | None = Form(None),
                        container: AppContainer = Depends(get_container)):
    result = await container.retriever.retrieve(query, ResourceType.MEMORY)
    context = "\n\n".join(item.content for item in result.documents)
    return {"context": context, "found": bool(context), "warnings": result.warnings}
