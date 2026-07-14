from typing import Any, TypedDict

from app.domain.entities import Citation, ScoredChunk


class ChatGraphState(TypedDict, total=False):
    query: str
    rewritten_query: str
    retry_count: int
    context: list[ScoredChunk]
    warnings: list[str]
    answer: str
    citations: list[Citation]
    memory_candidates: list[dict[str, Any]]
