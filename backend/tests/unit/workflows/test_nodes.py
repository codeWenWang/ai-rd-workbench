import asyncio

from app.domain.entities import ResourceType, RetrievalResult, ScoredChunk
from app.workflows.nodes import make_nodes


class FakeRetriever:
    async def retrieve(self, query: str, resource_type: ResourceType) -> RetrievalResult:
        if resource_type is ResourceType.MEMORY:
            return RetrievalResult([
                ScoredChunk(
                    chunk_id="memory-1",
                    content="我偏好使用 Python 3.11。",
                    score=1.0,
                    resource_type=ResourceType.MEMORY,
                    memory_id="memory-id",
                )
            ])
        return RetrievalResult([
            ScoredChunk(
                chunk_id=f"knowledge-{index}",
                content="项目后端使用 FastAPI。",
                score=1.0,
                resource_type=ResourceType.KNOWLEDGE,
                document_id=f"document-{index}",
            )
            for index in range(6)
        ])


class FakeModel:
    async def ainvoke(self, messages):
        return "Python 3.11"


def test_personal_preference_query_keeps_memory_in_generation_context() -> None:
    retrieve, *_ = make_nodes(FakeModel(), FakeRetriever())

    result = asyncio.run(retrieve({"query": "我偏好使用哪个 Python 版本？"}))

    assert result["context"][0].resource_type is ResourceType.MEMORY
    assert any(item.chunk_id == "memory-1" for item in result["context"][:6])
