from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Final, Protocol

from app.domain.entities import (
    CandidateStatus,
    Citation,
    Chunk,
    ComponentHealth,
    Conversation,
    IndexedChunk,
    KnowledgeDocument,
    Memory,
    MemoryCandidate,
    MemoryKind,
    Message,
    ModelMessage,
    MessageStatus,
    Project,
    ResourceStatus,
    ResourceType,
    RetrievalResult,
    ScoredChunk,
)


class _UnsetType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final[_UnsetType] = _UnsetType()


class ConversationRepository(Protocol):
    def create(self, title: str, project_id: str | None = None) -> Conversation: ...

    def get(self, conversation_id: str) -> Conversation | None: ...

    def list(
        self,
        *,
        include_archived: bool = False,
        project_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Conversation]: ...

    def rename(self, conversation_id: str, title: str) -> Conversation: ...

    def archive(self, conversation_id: str) -> Conversation: ...

    def delete(self, conversation_id: str) -> None: ...

    def add_message(
        self,
        conversation_id: str,
        *,
        role: str,
        content: str,
        status: MessageStatus = MessageStatus.PENDING,
    ) -> Message: ...

    def update_message(
        self,
        message_id: str,
        *,
        content: str | _UnsetType = UNSET,
        status: MessageStatus | _UnsetType = UNSET,
        error_code: str | None | _UnsetType = UNSET,
        error_message: str | None | _UnsetType = UNSET,
        citations: list[Citation] | _UnsetType = UNSET,
        warnings: list[str] | _UnsetType = UNSET,
    ) -> Message: ...

    def list_messages(self, conversation_id: str) -> list[Message]: ...


class ProjectRepository(Protocol):
    def create(
        self,
        *,
        name: str,
        root_path: str,
        source_type: str = "local",
    ) -> Project: ...

    def get(self, project_id: str) -> Project | None: ...

    def list(self) -> list[Project]: ...

    def delete(self, project_id: str) -> None: ...


class DocumentRepository(Protocol):
    def create(
        self,
        *,
        title: str,
        category: str,
        source_type: str,
        source_name: str,
        content_hash: str,
    ) -> KnowledgeDocument: ...

    def get(self, document_id: str) -> KnowledgeDocument | None: ...

    def list(
        self,
        *,
        status: ResourceStatus | None = None,
        category: str | None = None,
        query: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[KnowledgeDocument]: ...

    def update_status(
        self,
        document_id: str,
        status: ResourceStatus,
        *,
        error_message: str | None = None,
    ) -> KnowledgeDocument: ...

    def save_chunks(self, document_id: str, chunks: list[Chunk]) -> None: ...

    def list_chunks(self, document_id: str) -> list[Chunk]: ...

    def delete(self, document_id: str) -> None: ...

class MemoryRepository(Protocol):
    def create(
        self,
        *,
        title: str,
        content: str,
        kind: MemoryKind,
        source_type: str,
        source_conversation_id: str | None = None,
    ) -> Memory: ...

    def get(self, memory_id: str) -> Memory | None: ...

    def list_confirmed(
        self,
        *,
        include_archived: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Memory]: ...

    def update(
        self,
        memory_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        kind: MemoryKind | None = None,
    ) -> Memory: ...

    def archive(self, memory_id: str) -> Memory: ...

    def delete(self, memory_id: str) -> None: ...

    def create_candidate(
        self,
        *,
        title: str,
        content: str,
        kind: MemoryKind,
        conversation_id: str | None = None,
        message_id: str | None = None,
    ) -> MemoryCandidate: ...

    def list_candidates(
        self,
        *,
        status: CandidateStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[MemoryCandidate]: ...

    def get_candidate(self, candidate_id: str) -> MemoryCandidate | None: ...

    def update_candidate(
        self,
        candidate_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        kind: MemoryKind | None = None,
    ) -> MemoryCandidate: ...

    def update_candidate_status(
        self,
        candidate_id: str,
        status: CandidateStatus,
    ) -> MemoryCandidate: ...

    def save_chunks(self, memory_id: str, chunks: list[Chunk]) -> None: ...

    def list_chunks(self, memory_id: str) -> list[Chunk]: ...


class MigrationRepository(Protocol):
    def exists(self, namespace: str, vector_id: str) -> bool: ...

    def record(
        self,
        *,
        namespace: str,
        vector_id: str,
        target_type: ResourceType,
        target_id: str,
    ) -> None: ...

    def count(self, *, namespace: str | None = None) -> int: ...


class LexicalSearch(Protocol):
    def search(
        self,
        query: str,
        resource_type: ResourceType,
        limit: int,
    ) -> list[ScoredChunk]: ...


class ChatModel(Protocol):
    async def ainvoke(self, messages: list[ModelMessage]) -> str: ...

    def astream(self, messages: list[ModelMessage]) -> AsyncIterator[str]: ...


class EmbeddingModel(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class VectorIndex(Protocol):
    async def upsert(self, namespace: str, chunks: list[IndexedChunk]) -> None: ...

    async def delete(self, namespace: str, vector_ids: list[str]) -> None: ...

    async def query(
        self,
        namespace: str,
        vector: list[float],
        limit: int,
    ) -> list[ScoredChunk]: ...

    def list_ids(self, namespace: str) -> AsyncIterator[str]: ...

    async def fetch(
        self,
        namespace: str,
        vector_ids: list[str],
    ) -> list[IndexedChunk]: ...

    async def health(self) -> ComponentHealth: ...


class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        resource_type: ResourceType,
    ) -> RetrievalResult: ...
