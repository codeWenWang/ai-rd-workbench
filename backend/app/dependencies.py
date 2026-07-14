from functools import cached_property

from fastapi import Request

from app.application.chat import ChatUseCase
from app.application.documents import DocumentUseCase
from app.application.memories import MemoryUseCase
from app.application.migration import MigrationUseCase
from app.config import Settings, get_settings
from app.domain.entities import ResourceType
from app.infrastructure.db.repositories import (
    SqliteConversationRepository,
    SqliteDocumentRepository,
    SqliteMemoryRepository,
    SqliteMigrationRepository,
)
from app.infrastructure.db.session import Database
from app.infrastructure.llm.dashscope import DashScopeChatModel, DashScopeEmbeddingModel
from app.infrastructure.retrieval.fts import SqliteFtsSearch
from app.infrastructure.retrieval.hybrid import HybridRetriever
from app.infrastructure.vectorstores.pinecone import PineconeVectorIndex
from app.workflows.chat_graph import build_chat_graph


class AppContainer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.database = Database(self.settings.database_url)
        self.database.create_schema()
        self.conversations = SqliteConversationRepository(self.database.session_factory)
        self.documents = SqliteDocumentRepository(self.database.session_factory)
        self.memories = SqliteMemoryRepository(self.database.session_factory)
        self.migrations = SqliteMigrationRepository(self.database.session_factory)

    @cached_property
    def chat_model(self):
        return DashScopeChatModel(self.settings)

    @cached_property
    def embeddings(self):
        return DashScopeEmbeddingModel(self.settings)

    @cached_property
    def vector_index(self):
        return PineconeVectorIndex(self.settings)

    @cached_property
    def lexical_search(self):
        return SqliteFtsSearch(self.database.session_factory)

    @cached_property
    def retriever(self):
        return HybridRetriever(self.lexical_search, self.vector_index, self.embeddings,
                               namespaces={ResourceType.KNOWLEDGE: self.settings.pinecone_rag_namespace,
                                           ResourceType.MEMORY: self.settings.pinecone_memory_namespace})

    @cached_property
    def document_use_case(self):
        return DocumentUseCase(self.documents, self.embeddings, self.vector_index, self.settings)

    @cached_property
    def memory_use_case(self):
        return MemoryUseCase(self.memories, self.embeddings, self.vector_index, self.settings)

    @cached_property
    def graph(self):
        return build_chat_graph(self.chat_model, self.retriever)

    @cached_property
    def chat_use_case(self):
        return ChatUseCase(
            self.conversations,
            self.graph,
            self.memory_use_case,
            model=self.chat_model,
            retriever=self.retriever,
        )

    @cached_property
    def migration_use_case(self):
        return MigrationUseCase(self.documents, self.memories, self.migrations,
                                self.vector_index, self.settings)


def get_container(request: Request) -> AppContainer:
    return request.app.state.container
