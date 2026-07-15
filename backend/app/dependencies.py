from functools import cached_property
from pathlib import Path

from fastapi import Request

from app.application.chat import ChatUseCase
from app.application.documents import DocumentUseCase
from app.application.memories import MemoryUseCase
from app.application.artifacts import ArtifactUseCase
from app.application.models import ModelProviderUseCase
from app.application.project_analysis import ProjectAnalysisUseCase
from app.application.projects import ProjectUseCase
from app.application.migration import MigrationUseCase
from app.config import Settings, get_settings
from app.domain.entities import ResourceType
from app.infrastructure.db.repositories import (
    SqliteConversationRepository,
    SqliteDocumentRepository,
    SqliteMemoryRepository,
    SqliteMigrationRepository,
    SqliteModelProviderRepository,
    SqliteProjectAnalysisRepository,
    SqliteProjectRepository,
)
from app.infrastructure.db.session import Database
from app.infrastructure.llm.dashscope import DashScopeChatModel, DashScopeEmbeddingModel
from app.infrastructure.llm.gateway import ModelGateway
from app.infrastructure.projects.parsers import ParserRegistry
from app.infrastructure.projects.scanner import LocalProjectScanner
from app.infrastructure.projects.remote_git import RemoteGitRepositoryManager
from app.infrastructure.retrieval.fts import SqliteFtsSearch
from app.infrastructure.retrieval.hybrid import HybridRetriever
from app.infrastructure.retrieval.project import ProjectIndexer, ProjectRetriever
from app.infrastructure.security.secrets import LocalSecretStore
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
        self.projects = SqliteProjectRepository(self.database.session_factory)
        self.project_analysis = SqliteProjectAnalysisRepository(self.database.session_factory)
        self.model_providers = SqliteModelProviderRepository(self.database.session_factory)
        self.secret_store = LocalSecretStore(_data_dir(self.settings.database_url))
        self.remote_git = RemoteGitRepositoryManager(
            self.settings.git_cache_dir,
            clone_timeout_seconds=self.settings.git_clone_timeout_seconds,
            update_timeout_seconds=self.settings.git_update_timeout_seconds,
        )
        self.model_provider_use_case = ModelProviderUseCase(
            self.model_providers, self.secret_store
        )
        self.model_provider_use_case.ensure_dashscope_default(self.settings)

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
    def project_retriever(self):
        return ProjectRetriever(
            self.project_analysis, self.embeddings, self.vector_index,
            limit=self.settings.rag_top_k,
        )

    @cached_property
    def project_indexer(self):
        return ProjectIndexer(self.project_analysis, self.embeddings, self.vector_index)

    @cached_property
    def project_use_case(self):
        return ProjectUseCase(self.projects, self.remote_git)

    @cached_property
    def project_analysis_use_case(self):
        return ProjectAnalysisUseCase(
            self.projects,
            self.project_analysis,
            LocalProjectScanner(),
            ParserRegistry(),
        )

    @cached_property
    def artifact_use_case(self):
        return ArtifactUseCase(self.projects, self.project_analysis)

    @cached_property
    def model_gateway(self):
        gateway = ModelGateway()
        self.model_provider_use_case.register_all(gateway)
        return gateway

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
            project_retriever=self.project_retriever,
            model_gateway=self.model_gateway,
        )

    @cached_property
    def migration_use_case(self):
        return MigrationUseCase(self.documents, self.memories, self.migrations,
                                self.vector_index, self.settings)


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def _data_dir(database_url: str) -> Path:
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///" )).resolve().parent
    return Path(__file__).resolve().parents[1] / "data"
