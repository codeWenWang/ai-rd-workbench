from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.api.serializers import serialize
from app.dependencies import AppContainer, get_container
from app.domain.entities import ResourceStatus


router = APIRouter(tags=["documents"])


class DocumentTextRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str = ""
    category: str = "general"


class DocumentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    category: str | None = Field(default=None, min_length=1, max_length=100)


@router.get("/api/documents")
def list_documents(status: ResourceStatus | None = None, category: str | None = None,
                   query: str | None = None, offset: int = 0, limit: int = 100,
                   container: AppContainer = Depends(get_container)):
    items = container.document_use_case.list(status=status, category=category, query=query,
                                             offset=offset, limit=limit)
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/api/documents/{document_id}")
def get_document(document_id: str, container: AppContainer = Depends(get_container)):
    document = container.document_use_case.get(document_id)
    result = serialize(document)
    result["chunks"] = [serialize(item) for item in container.documents.list_chunks(document_id)]
    return result


@router.post("/api/documents/text")
@router.post("/api/knowledge/text")
async def add_document_text(request: DocumentTextRequest, container: AppContainer = Depends(get_container)):
    document = await container.document_use_case.ingest_text(request.text, title=request.title,
                                                              category=request.category)
    return {"success": True, "message": "Document indexed", "count": len(container.documents.list_chunks(document.id)),
            "document": serialize(document), "document_id": document.id}


@router.post("/api/documents/pdf")
@router.post("/api/knowledge/pdf")
async def add_document_pdf(file: UploadFile = File(...), category: str = Form("general"),
                           container: AppContainer = Depends(get_container)):
    document = await container.document_use_case.ingest_pdf(await file.read(), filename=file.filename or "upload.pdf",
                                                             category=category)
    return {"success": True, "message": "Document indexed", "count": len(container.documents.list_chunks(document.id)),
            "document": serialize(document), "document_id": document.id}


@router.patch("/api/documents/{document_id}")
def update_document(document_id: str, patch: DocumentPatch,
                    container: AppContainer = Depends(get_container)):
    return serialize(container.document_use_case.update(document_id, **patch.model_dump(exclude_unset=True)))


@router.post("/api/documents/{document_id}/reindex")
async def reindex_document(document_id: str, container: AppContainer = Depends(get_container)):
    return serialize(await container.document_use_case.reindex(document_id))


@router.delete("/api/documents/{document_id}")
async def delete_document(document_id: str, container: AppContainer = Depends(get_container)):
    await container.document_use_case.delete(document_id)
    return {"success": True}
