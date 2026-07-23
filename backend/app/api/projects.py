import asyncio
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.serializers import serialize
from app.dependencies import AppContainer, get_container
from app.domain.errors import ResourceNotFound
from app.infrastructure.retrieval.project import project_namespace


router = APIRouter(prefix="/api/projects", tags=["projects"])


def _choose_directory() -> str:
    """Open the native folder picker for the local-only desktop workflow."""
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return filedialog.askdirectory(title="选择要连接的项目文件夹") or ""
    finally:
        root.destroy()


@router.post("/select-directory")
async def select_directory():
    return {"path": await asyncio.to_thread(_choose_directory)}


class ProjectCreate(BaseModel):
    name: str = Field(default="", max_length=300)
    source_type: Literal["local", "github", "gitee"] = "local"
    root_path: str = Field(default="", max_length=1000)
    repository_url: str = Field(default="", max_length=1000)


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=300)


@router.post("")
def create_project(payload: ProjectCreate, container: AppContainer = Depends(get_container)):
    return serialize(container.project_use_case.create(
        payload.name,
        payload.root_path,
        source_type=payload.source_type,
        repository_url=payload.repository_url,
    ))


@router.get("")
def list_projects(container: AppContainer = Depends(get_container)):
    items = container.project_use_case.list()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.get("/{project_id}")
def get_project(project_id: str, container: AppContainer = Depends(get_container)):
    project = container.project_use_case.get(project_id)
    if not project:
        raise ResourceNotFound("project not found")
    return serialize(project)


@router.patch("/{project_id}")
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    container: AppContainer = Depends(get_container),
):
    return serialize(container.project_use_case.update(project_id, name=payload.name))


@router.delete("/{project_id}")
async def delete_project(project_id: str, container: AppContainer = Depends(get_container)):
    chunks = container.project_analysis.list_chunks(project_id)
    warnings = []
    if chunks:
        try:
            await container.vector_index.delete(
                project_namespace(project_id),
                [item.vector_id or item.id for item in chunks],
            )
        except Exception:
            warnings.append("project_vector_delete_unavailable")
    await asyncio.to_thread(container.project_use_case.delete, project_id)
    return {"success": True, "warnings": warnings}


@router.post("/{project_id}/scan")
async def scan_project(project_id: str, container: AppContainer = Depends(get_container)):
    warnings = await asyncio.to_thread(
        container.project_use_case.prepare_for_scan,
        project_id,
    )
    summary = await asyncio.to_thread(container.project_analysis_use_case.scan, project_id)
    indexed_chunks = 0
    try:
        indexed_chunks = await asyncio.wait_for(
            container.project_indexer.index(project_id),
            timeout=container.settings.project_index_timeout_seconds,
        )
    except TimeoutError:
        warnings.append("project_semantic_index_timeout")
    except Exception:
        warnings.append("project_semantic_index_unavailable")
    return {
        **serialize(summary),
        "indexed_chunks": indexed_chunks,
        "warnings": list(dict.fromkeys(warnings)),
    }


@router.get("/{project_id}/files")
def list_project_files(project_id: str, container: AppContainer = Depends(get_container)):
    items = container.project_analysis.list_files(project_id)
    return {
        "items": [
            {
                "id": item.id,
                "project_id": item.project_id,
                "relative_path": item.relative_path,
                "language": item.language,
                "content_hash": item.content_hash,
                "size_bytes": item.size_bytes,
                "excerpt": item.content[:300],
            }
            for item in items
        ],
        "total": len(items),
    }


@router.get("/{project_id}/files/{file_id}")
def get_project_file(project_id: str, file_id: str, container: AppContainer = Depends(get_container)):
    item = next(
        (file for file in container.project_analysis.list_files(project_id) if file.id == file_id),
        None,
    )
    if not item:
        raise ResourceNotFound("project file not found")
    return {
        "id": item.id,
        "project_id": item.project_id,
        "relative_path": item.relative_path,
        "language": item.language,
        "content": item.content,
        "size_bytes": item.size_bytes,
    }


@router.get("/{project_id}/routes")
def list_project_routes(project_id: str, container: AppContainer = Depends(get_container)):
    items = container.project_analysis.list_routes(project_id)
    files = {
        item.id: item.relative_path
        for item in container.project_analysis.list_files(project_id)
    }
    return {
        "items": [
            {**serialize(item), "source_path": files.get(item.project_file_id, "")}
            for item in items
        ],
        "total": len(items),
    }
