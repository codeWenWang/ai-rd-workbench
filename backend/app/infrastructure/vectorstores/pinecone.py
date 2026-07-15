import asyncio
from collections.abc import AsyncIterator

from app.config import Settings
from app.domain.entities import ComponentHealth, IndexedChunk, ResourceType, ScoredChunk
from app.domain.errors import ExternalServiceError


class PineconeVectorIndex:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._index = None

    def _get_index(self):
        if not self.settings.pinecone_api_key:
            raise ExternalServiceError("Pinecone API key is not configured")
        if self._index is None:
            from pinecone import Pinecone

            client = Pinecone(api_key=self.settings.pinecone_api_key)
            kwargs = {"host": self.settings.pinecone_host} if self.settings.pinecone_host else {}
            self._index = client.Index(self.settings.pinecone_index_name, **kwargs)
        return self._index

    async def upsert(self, namespace: str, chunks: list[IndexedChunk]) -> None:
        if not chunks:
            return
        vectors = [
            {
                "id": item.vector_id,
                "values": item.values,
                "metadata": _sanitize_metadata(item.metadata),
            }
            for item in chunks
        ]
        try:
            await asyncio.to_thread(
                lambda: self._get_index().upsert(vectors=vectors, namespace=namespace)
            )
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError("vector upsert failed") from exc

    async def delete(self, namespace: str, vector_ids: list[str]) -> None:
        if not vector_ids:
            return
        try:
            await asyncio.to_thread(
                lambda: self._get_index().delete(ids=vector_ids, namespace=namespace)
            )
        except Exception as exc:
            raise ExternalServiceError("vector delete failed") from exc

    async def query(self, namespace: str, vector: list[float], limit: int) -> list[ScoredChunk]:
        try:
            result = await asyncio.to_thread(
                lambda: self._get_index().query(
                    vector=vector,
                    top_k=limit,
                    namespace=namespace,
                    include_metadata=True,
                )
            )
        except Exception as exc:
            raise ExternalServiceError("semantic retrieval unavailable") from exc
        matches = result.get("matches", []) if isinstance(result, dict) else result.matches
        output = []
        for match in matches:
            metadata = match.get("metadata", {}) if isinstance(match, dict) else (match.metadata or {})
            match_id = match.get("id") if isinstance(match, dict) else match.id
            score = match.get("score", 0.0) if isinstance(match, dict) else match.score
            resource_value = metadata.get("resource_type")
            try:
                resource_type = ResourceType(resource_value) if resource_value else (
                    ResourceType.MEMORY
                    if namespace == self.settings.pinecone_memory_namespace
                    else ResourceType.KNOWLEDGE
                )
            except ValueError:
                resource_type = ResourceType.KNOWLEDGE
            output.append(ScoredChunk(
                chunk_id=str(metadata.get("chunk_id") or match_id), content=str(metadata.get("text") or metadata.get("content") or ""),
                score=float(score), title=metadata.get("title"), category=metadata.get("category"),
                page_number=_int_or_none(metadata.get("page_number")), resource_type=resource_type,
                document_id=metadata.get("document_id") if resource_type is ResourceType.KNOWLEDGE else None,
                memory_id=metadata.get("memory_id") if resource_type is ResourceType.MEMORY else None,
                vector_id=str(match_id), metadata=dict(metadata),
            ))
        return output

    async def list_ids(self, namespace: str) -> AsyncIterator[str]:
        try:
            pages = await asyncio.to_thread(
                lambda: list(self._get_index().list(namespace=namespace))
            )
            for page in pages:
                ids = page.get("vectors", page) if isinstance(page, dict) else page
                for item in ids:
                    yield str(item.get("id") if isinstance(item, dict) else item)
        except Exception as exc:
            raise ExternalServiceError("vector listing failed") from exc

    async def fetch(self, namespace: str, vector_ids: list[str]) -> list[IndexedChunk]:
        if not vector_ids:
            return []
        try:
            result = await asyncio.to_thread(
                lambda: self._get_index().fetch(ids=vector_ids, namespace=namespace)
            )
        except Exception as exc:
            raise ExternalServiceError("vector fetch failed") from exc
        vectors = result.get("vectors", {}) if isinstance(result, dict) else result.vectors
        return [IndexedChunk(str(vector_id), list(_field(value, "values", [])), dict(_field(value, "metadata", {}) or {}))
                for vector_id, value in vectors.items()]

    async def health(self) -> ComponentHealth:
        try:
            stats = await asyncio.to_thread(
                lambda: self._get_index().describe_index_stats()
            )
            dimension = _field(stats, "dimension", None)
            return ComponentHealth("pinecone", True, details={"dimension": dimension})
        except Exception:
            return ComponentHealth("pinecone", False, "unavailable")


def _field(value, name: str, default):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _sanitize_metadata(metadata: dict) -> dict:
    """Return only metadata values accepted by Pinecone."""
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def _int_or_none(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
