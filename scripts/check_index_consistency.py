import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import func, select


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.dependencies import AppContainer  # noqa: E402
from app.infrastructure.db.models import ChunkModel  # noqa: E402


async def main() -> int:
    container = AppContainer()
    with container.database.session_factory() as session:
        local_chunks = int(session.scalar(select(func.count()).select_from(ChunkModel)) or 0)
        local_vectors = set(session.scalars(select(ChunkModel.vector_id).where(ChunkModel.vector_id.is_not(None))))
    remote: dict[str, int | str] = {}
    remote_ids: set[str] = set()
    try:
        for namespace in (container.settings.pinecone_rag_namespace, container.settings.pinecone_memory_namespace):
            ids = [item async for item in container.vector_index.list_ids(namespace)]
            remote[namespace] = len(ids)
            remote_ids.update(ids)
        status = "ok"
    except Exception:
        status = "degraded"
        remote["error"] = "pinecone_unavailable"
    output = {"status": status, "local_chunks": local_chunks,
              "local_vector_ids": len(local_vectors), "remote": remote,
              "local_ids_missing_remotely": sorted(local_vectors - remote_ids) if status == "ok" else [],
              "remote_ids_missing_locally": sorted(remote_ids - local_vectors) if status == "ok" else []}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    consistent = not output["local_ids_missing_remotely"] and not output["remote_ids_missing_locally"]
    return 0 if status == "ok" and consistent else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
