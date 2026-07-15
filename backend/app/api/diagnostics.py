import asyncio

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select, text

from app.dependencies import AppContainer, get_container
from app.domain.entities import ComponentHealth
from app.infrastructure.db.models import (
    ChunkModel,
    ConversationModel,
    DocumentModel,
    MemoryModel,
    MigrationRecordModel,
)


router = APIRouter(tags=["diagnostics"])


async def _pinecone_health(container: AppContainer) -> ComponentHealth:
    try:
        return await asyncio.wait_for(
            container.vector_index.health(),
            timeout=container.settings.diagnostics_timeout_seconds,
        )
    except TimeoutError:
        return ComponentHealth("pinecone", False, "timeout")


@router.get("/api/health/live")
def liveness():
    return {"status": "ok"}


@router.get("/api/health")
def legacy_health():
    return {"status": "ok"}


@router.get("/api/health/ready")
async def readiness(response: Response, container: AppContainer = Depends(get_container)):
    components = {}
    try:
        with container.database.session_factory() as session:
            session.execute(text("SELECT 1"))
        components["sqlite"] = {"status": "ok"}
    except Exception:
        components["sqlite"] = {"status": "error", "message": "unavailable"}
    pinecone = await _pinecone_health(container)
    components["pinecone"] = {"status": "ok" if pinecone.ok else "error",
                               "message": pinecone.message, "details": pinecone.details}
    configured = bool(container.settings.dashscope_api_key)
    components["dashscope"] = {"status": "ok" if configured else "error",
                                "message": None if configured else "not configured"}
    ready = all(item["status"] == "ok" for item in components.values())
    response.status_code = 200 if ready else 503
    return {"status": "ready" if ready else "degraded", "components": components}


@router.get("/api/diagnostics")
async def diagnostics(container: AppContainer = Depends(get_container)):
    with container.database.session_factory() as session:
        counts = {
            "conversations": session.scalar(select(func.count()).select_from(ConversationModel)) or 0,
            "documents": session.scalar(select(func.count()).select_from(DocumentModel)) or 0,
            "memories": session.scalar(select(func.count()).select_from(MemoryModel)) or 0,
            "chunks": session.scalar(select(func.count()).select_from(ChunkModel)) or 0,
        }
        local_vector_ids = set(
            session.scalars(select(ChunkModel.vector_id).where(ChunkModel.vector_id.is_not(None)))
        )
        migration_count = session.scalar(select(func.count()).select_from(MigrationRecordModel)) or 0
    health = await _pinecone_health(container)
    namespaces = {}
    remote_vector_ids: set[str] = set()
    if health.ok:
        try:
            async def collect_vector_ids() -> None:
                for namespace in (
                    container.settings.pinecone_rag_namespace,
                    container.settings.pinecone_memory_namespace,
                ):
                    ids = [item async for item in container.vector_index.list_ids(namespace)]
                    namespaces[namespace] = len(ids)
                    remote_vector_ids.update(ids)

            await asyncio.wait_for(
                collect_vector_ids(),
                timeout=container.settings.diagnostics_timeout_seconds,
            )
        except TimeoutError:
            health = ComponentHealth("pinecone", False, "vector listing timeout", health.details)
        except Exception:
            health = type(health)(health.name, False, "vector listing unavailable", health.details)

    configured = bool(container.settings.dashscope_api_key)
    components = {
        "sqlite": {"status": "ok", "message": f"{counts['chunks']} 个片段"},
        "pinecone": {
            "status": "ok" if health.ok else "error",
            "message": health.message,
            "details": health.details,
        },
        "dashscope": {
            "status": "ok" if configured else "error",
            "message": f"{container.settings.llm_model} / {container.settings.embedding_model}",
        },
    }
    missing = sorted(local_vector_ids - remote_vector_ids) if health.ok else []
    orphaned = sorted(remote_vector_ids - local_vector_ids) if health.ok else []
    return {
        "status": "ok" if all(item["status"] == "ok" for item in components.values()) else "degraded",
        "components": components,
        "database": {"status": "ok", "counts": counts},
        "vector": {
            "status": "ok" if health.ok else "error",
            "name": container.settings.pinecone_index_name,
            "dimension": (health.details or {}).get("dimension", container.settings.embedding_dimension),
            "namespaces": namespaces,
        },
        "consistency": {
            "consistent": health.ok and not missing and not orphaned,
            "sqlite_count": len(local_vector_ids),
            "pinecone_count": len(remote_vector_ids),
            "missing_vectors": len(missing),
            "orphan_vectors": len(orphaned),
        },
        "migration": {"status": "completed" if migration_count else "not_started", "count": migration_count},
        "configuration": {
            "llm_model": container.settings.llm_model,
            "embedding_model": container.settings.embedding_model,
            "embedding_dimension": container.settings.embedding_dimension,
            "rag_namespace": container.settings.pinecone_rag_namespace,
            "memory_namespace": container.settings.pinecone_memory_namespace,
        },
    }
