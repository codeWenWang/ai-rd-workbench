import asyncio

from app.domain.entities import ResourceType, RetrievalResult, ScoredChunk


def reciprocal_rank_fusion(*rankings: list[ScoredChunk], limit: int = 6, k: int = 60) -> list[ScoredChunk]:
    scores: dict[str, float] = {}
    chunks: dict[str, ScoredChunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
            chunks[chunk.chunk_id] = chunk
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:limit]
    return [ScoredChunk(**{**chunks[item].__dict__, "score": scores[item]}) if hasattr(chunks[item], "__dict__")
            else _with_score(chunks[item], scores[item]) for item in ordered]


def _with_score(chunk: ScoredChunk, score: float) -> ScoredChunk:
    return ScoredChunk(chunk_id=chunk.chunk_id, content=chunk.content, score=score, title=chunk.title,
                       category=chunk.category, page_number=chunk.page_number, resource_type=chunk.resource_type,
                       document_id=chunk.document_id, memory_id=chunk.memory_id, vector_id=chunk.vector_id,
                       metadata=dict(chunk.metadata))


class HybridRetriever:
    def __init__(self, lexical, vector_index, embeddings, *, namespaces: dict[ResourceType, str], limit: int = 6) -> None:
        self.lexical = lexical
        self.vector_index = vector_index
        self.embeddings = embeddings
        self.namespaces = namespaces
        self.limit = limit

    async def retrieve(self, query: str, resource_type: ResourceType) -> RetrievalResult:
        lexical = self.lexical.search(query, resource_type, self.limit * 2)
        warnings: list[str] = []
        try:
            vector = await self.embeddings.embed_query(query)
            dense = await self.vector_index.query(self.namespaces[resource_type], vector, self.limit * 2)
        except Exception:
            dense = []
            warnings.append("semantic_retrieval_unavailable")
        return RetrievalResult(reciprocal_rank_fusion(dense, lexical, limit=self.limit), warnings)
