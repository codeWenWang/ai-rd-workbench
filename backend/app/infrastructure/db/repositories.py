from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.domain.entities import (
    CandidateStatus,
    AnalysisArtifact,
    Chunk,
    Citation,
    Conversation,
    ConversationStatus,
    KnowledgeDocument,
    Memory,
    MemoryCandidate,
    MemoryKind,
    MemoryStatus,
    Message,
    MessageStatus,
    ModelProvider,
    Project,
    ProjectChunk,
    ProjectFile,
    ProjectRelation,
    ProjectRoute,
    ProjectSymbol,
    ResourceStatus,
    ResourceType,
    ScoredChunk,
)
from app.domain.errors import ResourceNotFound
from app.domain.ports import UNSET
from app.infrastructure.db.models import (
    CandidateModel,
    AnalysisArtifactModel,
    ChunkModel,
    ConversationModel,
    DocumentModel,
    MemoryModel,
    MessageModel,
    ModelProviderModel,
    MigrationRecordModel,
    ProjectModel,
    ProjectFileModel,
    ProjectChunkModel,
    ProjectRelationModel,
    ProjectRouteModel,
    ProjectSymbolModel,
)


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RepositoryBase:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions


class SqliteModelProviderRepository(RepositoryBase):
    def create(
        self,
        *,
        name: str,
        provider_type: str,
        base_url: str,
        model_name: str,
        secret_ref: str,
        is_default: bool = False,
    ) -> ModelProvider:
        with self.sessions.begin() as session:
            if is_default:
                for existing in session.scalars(
                    select(ModelProviderModel).where(ModelProviderModel.is_default.is_(True))
                ):
                    existing.is_default = False
            row = ModelProviderModel(
                id=_id(), name=name, provider_type=provider_type, base_url=base_url,
                model_name=model_name, secret_ref=secret_ref,
                is_default=is_default,
            )
            session.add(row)
        return self._entity(row)

    def get(self, provider_id: str) -> ModelProvider | None:
        with self.sessions() as session:
            row = session.get(ModelProviderModel, provider_id)
            return self._entity(row) if row else None

    def list(self, *, enabled_only: bool = False) -> list[ModelProvider]:
        with self.sessions() as session:
            query = select(ModelProviderModel)
            if enabled_only:
                query = query.where(ModelProviderModel.enabled.is_(True))
            rows = session.scalars(
                query.order_by(ModelProviderModel.is_default.desc(), ModelProviderModel.created_at)
            )
            return [self._entity(row) for row in rows]

    def delete(self, provider_id: str) -> None:
        with self.sessions.begin() as session:
            row = session.get(ModelProviderModel, provider_id)
            if not row:
                raise ResourceNotFound("model provider not found")
            session.delete(row)

    @staticmethod
    def _entity(row: ModelProviderModel) -> ModelProvider:
        return ModelProvider(
            id=row.id, name=row.name, provider_type=row.provider_type,
            base_url=row.base_url, model_name=row.model_name,
            secret_ref=row.secret_ref, enabled=row.enabled,
            is_default=row.is_default, created_at=row.created_at,
            updated_at=row.updated_at,
        )


class SqliteProjectRepository(RepositoryBase):
    def create(self, *, name: str, root_path: str, source_type: str = "local") -> Project:
        normalized = str(Path(root_path).expanduser().resolve())
        with self.sessions.begin() as session:
            row = ProjectModel(
                id=_id(),
                name=name.strip() or Path(normalized).name,
                root_path=normalized,
                source_type=source_type,
            )
            session.add(row)
        return self._entity(row)

    def get(self, project_id: str) -> Project | None:
        with self.sessions() as session:
            row = session.get(ProjectModel, project_id)
            return self._entity(row) if row else None

    def list(self) -> list[Project]:
        with self.sessions() as session:
            rows = session.scalars(select(ProjectModel).order_by(ProjectModel.created_at, ProjectModel.id))
            return [self._entity(row) for row in rows]

    def delete(self, project_id: str) -> None:
        with self.sessions.begin() as session:
            row = session.get(ProjectModel, project_id)
            if not row:
                raise ResourceNotFound("project not found")
            session.delete(row)

    def update_scan(
        self,
        project_id: str,
        *,
        revision: str,
        tech_stack: list[str],
        status: str = "ready",
    ) -> Project:
        with self.sessions.begin() as session:
            row = session.get(ProjectModel, project_id)
            if not row:
                raise ResourceNotFound("project not found")
            row.source_revision = revision
            row.tech_stack_json = json.dumps(tech_stack, ensure_ascii=False)
            row.status = status
            row.last_scanned_at = _now()
            row.updated_at = _now()
        return self._entity(row)

    @staticmethod
    def _entity(row: ProjectModel) -> Project:
        return Project(
            id=row.id,
            name=row.name,
            root_path=row.root_path,
            source_type=row.source_type,
            status=row.status,
            source_revision=row.source_revision,
            tech_stack=json.loads(row.tech_stack_json or "[]"),
            last_scanned_at=row.last_scanned_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class SqliteProjectAnalysisRepository(RepositoryBase):
    def replace_scan(self, project_id: str, items) -> None:
        with self.sessions.begin() as session:
            if not session.get(ProjectModel, project_id):
                raise ResourceNotFound("project not found")
            session.execute(delete(ProjectRouteModel).where(ProjectRouteModel.project_id == project_id))
            session.execute(delete(ProjectSymbolModel).where(ProjectSymbolModel.project_id == project_id))
            session.execute(delete(ProjectRelationModel).where(ProjectRelationModel.project_id == project_id))
            old_chunk_ids = list(session.scalars(
                select(ProjectChunkModel.id).where(ProjectChunkModel.project_id == project_id)
            ))
            for chunk_id in old_chunk_ids:
                session.execute(
                    text("DELETE FROM project_chunks_fts WHERE chunk_id=:id"),
                    {"id": chunk_id},
                )
            session.execute(delete(ProjectChunkModel).where(ProjectChunkModel.project_id == project_id))
            session.execute(delete(ProjectFileModel).where(ProjectFileModel.project_id == project_id))
            for scanned, parsed in items:
                file_id = _id()
                session.add(ProjectFileModel(
                    id=file_id,
                    project_id=project_id,
                    relative_path=scanned.relative_path,
                    language=scanned.language,
                    content_hash=scanned.content_hash,
                    content=scanned.content,
                    size_bytes=scanned.size_bytes,
                    modified_ns=scanned.modified_ns,
                ))
                session.flush()
                for symbol in parsed.symbols:
                    session.add(ProjectSymbolModel(
                        id=_id(), project_id=project_id, project_file_id=file_id,
                        name=symbol.name, kind=symbol.kind, line_number=symbol.line_number,
                        end_line_number=symbol.end_line_number,
                    ))
                for route in parsed.routes:
                    session.add(ProjectRouteModel(
                        id=_id(), project_id=project_id, project_file_id=file_id,
                        method=route.method, path=route.path, handler=route.handler,
                        line_number=route.line_number,
                    ))
                for target in parsed.imports:
                    session.add(ProjectRelationModel(
                        id=_id(), project_id=project_id, source_path=scanned.relative_path,
                        target=target, kind="import", inferred=False,
                    ))
                for target in parsed.calls:
                    session.add(ProjectRelationModel(
                        id=_id(), project_id=project_id, source_path=scanned.relative_path,
                        target=target, kind="call", inferred=True,
                    ))
                for chunk_index, (chunk_content, start_line, end_line) in enumerate(
                    _split_source(scanned.content)
                ):
                    chunk_id = sha256(
                        f"{project_id}:{scanned.relative_path}:{scanned.content_hash}:{chunk_index}".encode("utf-8")
                    ).hexdigest()
                    session.add(ProjectChunkModel(
                        id=chunk_id,
                        project_id=project_id,
                        project_file_id=file_id,
                        relative_path=scanned.relative_path,
                        content=chunk_content,
                        start_line=start_line,
                        end_line=end_line,
                        vector_id=chunk_id,
                    ))
                    session.execute(
                        text(
                            "INSERT INTO project_chunks_fts(chunk_id,project_id,content,relative_path) "
                            "VALUES(:chunk_id,:project_id,:content,:relative_path)"
                        ),
                        {
                            "chunk_id": chunk_id,
                            "project_id": project_id,
                            "content": chunk_content,
                            "relative_path": scanned.relative_path,
                        },
                    )

    def list_files(self, project_id: str) -> list[ProjectFile]:
        with self.sessions() as session:
            rows = session.scalars(
                select(ProjectFileModel).where(ProjectFileModel.project_id == project_id)
                .order_by(ProjectFileModel.relative_path)
            )
            return [ProjectFile(
                row.id, row.project_id, row.relative_path, row.language,
                row.content_hash, row.content, row.size_bytes, row.modified_ns,
            ) for row in rows]

    def list_symbols(self, project_id: str) -> list[ProjectSymbol]:
        with self.sessions() as session:
            rows = session.scalars(
                select(ProjectSymbolModel).where(ProjectSymbolModel.project_id == project_id)
                .order_by(ProjectSymbolModel.name, ProjectSymbolModel.line_number)
            )
            return [ProjectSymbol(
                row.id, row.project_id, row.project_file_id, row.name, row.kind,
                row.line_number, row.end_line_number,
            ) for row in rows]

    def list_routes(self, project_id: str) -> list[ProjectRoute]:
        with self.sessions() as session:
            rows = session.scalars(
                select(ProjectRouteModel).where(ProjectRouteModel.project_id == project_id)
                .order_by(ProjectRouteModel.path, ProjectRouteModel.method)
            )
            return [ProjectRoute(
                row.id, row.project_id, row.project_file_id, row.method, row.path,
                row.handler, row.line_number,
            ) for row in rows]

    def list_relations(self, project_id: str) -> list[ProjectRelation]:
        with self.sessions() as session:
            rows = session.scalars(
                select(ProjectRelationModel).where(ProjectRelationModel.project_id == project_id)
                .order_by(ProjectRelationModel.source_path, ProjectRelationModel.kind, ProjectRelationModel.target)
            )
            return [ProjectRelation(
                row.id, row.project_id, row.source_path, row.target, row.kind, row.inferred,
            ) for row in rows]

    def search_chunks(self, project_id: str, query: str, limit: int = 6) -> list[ProjectChunk]:
        fts_query = _fts_query(query)
        if not fts_query:
            return []
        with self.sessions() as session:
            rows = session.execute(text(
                "SELECT pc.id,pc.project_id,pc.project_file_id,pc.relative_path,pc.content,"
                "pc.start_line,pc.end_line,pc.vector_id "
                "FROM project_chunks_fts f JOIN project_chunks pc ON pc.id=f.chunk_id "
                "WHERE f.project_id=:project_id AND project_chunks_fts MATCH :query "
                "ORDER BY bm25(project_chunks_fts) LIMIT :limit"
            ), {"project_id": project_id, "query": fts_query, "limit": limit}).mappings()
            return [ProjectChunk(**dict(row)) for row in rows]

    def list_chunks(self, project_id: str) -> list[ProjectChunk]:
        with self.sessions() as session:
            rows = session.scalars(
                select(ProjectChunkModel).where(ProjectChunkModel.project_id == project_id)
                .order_by(ProjectChunkModel.relative_path, ProjectChunkModel.start_line)
            )
            return [ProjectChunk(
                row.id, row.project_id, row.project_file_id, row.relative_path,
                row.content, row.start_line, row.end_line, row.vector_id,
            ) for row in rows]

    def save_artifact(
        self,
        *,
        project_id: str,
        artifact_type: str,
        format: str,
        content: str,
        source_revision: str,
    ) -> AnalysisArtifact:
        with self.sessions.begin() as session:
            row = AnalysisArtifactModel(
                id=_id(), project_id=project_id, artifact_type=artifact_type,
                format=format, content=content, source_revision=source_revision,
            )
            session.add(row)
        return self._artifact(row)

    def get_artifact(self, artifact_id: str) -> AnalysisArtifact | None:
        with self.sessions() as session:
            row = session.get(AnalysisArtifactModel, artifact_id)
            return self._artifact(row) if row else None

    def list_artifacts(self, project_id: str) -> list[AnalysisArtifact]:
        with self.sessions() as session:
            rows = session.scalars(
                select(AnalysisArtifactModel)
                .where(AnalysisArtifactModel.project_id == project_id)
                .order_by(AnalysisArtifactModel.updated_at.desc())
            )
            return [self._artifact(row) for row in rows]

    def mark_artifacts_stale(self, project_id: str) -> None:
        with self.sessions.begin() as session:
            rows = session.scalars(
                select(AnalysisArtifactModel).where(
                    AnalysisArtifactModel.project_id == project_id,
                    AnalysisArtifactModel.status == "ready",
                )
            )
            for row in rows:
                row.status = "stale"
                row.updated_at = _now()

    @staticmethod
    def _artifact(row: AnalysisArtifactModel) -> AnalysisArtifact:
        return AnalysisArtifact(
            row.id, row.project_id, row.artifact_type, row.format, row.content,
            row.source_revision, row.status, row.created_at, row.updated_at,
        )


class SqliteConversationRepository(RepositoryBase):
    def create(self, title: str = "New conversation", project_id: str | None = None) -> Conversation:
        with self.sessions.begin() as session:
            row = ConversationModel(
                id=_id(),
                title=title.strip() or "New conversation",
                project_id=project_id,
            )
            session.add(row)
        return self._entity(row)

    def get(self, conversation_id: str) -> Conversation | None:
        with self.sessions() as session:
            row = session.get(ConversationModel, conversation_id)
            return self._entity(row) if row else None

    def list(self, *, include_archived=False, project_id=None, offset=0, limit=100) -> list[Conversation]:
        with self.sessions() as session:
            query = select(ConversationModel)
            if not include_archived:
                query = query.where(ConversationModel.status == "active")
            if project_id is not None:
                query = query.where(ConversationModel.project_id == project_id)
            rows = session.scalars(
                query.order_by(ConversationModel.updated_at.desc()).offset(offset).limit(limit)
            )
            return [self._entity(row) for row in rows]

    def rename(self, conversation_id: str, title: str) -> Conversation:
        with self.sessions.begin() as session:
            row = self._require(session, conversation_id)
            row.title = title.strip() or row.title
            row.updated_at = _now()
        return self._entity(row)

    def archive(self, conversation_id: str) -> Conversation:
        with self.sessions.begin() as session:
            row = self._require(session, conversation_id)
            row.status = ConversationStatus.ARCHIVED.value
            row.updated_at = _now()
        return self._entity(row)

    def delete(self, conversation_id: str) -> None:
        with self.sessions.begin() as session:
            row = self._require(session, conversation_id)
            session.delete(row)

    def add_message(self, conversation_id: str, *, role: str, content: str, status=MessageStatus.PENDING) -> Message:
        with self.sessions.begin() as session:
            conversation = self._require(session, conversation_id)
            row = MessageModel(
                id=_id(), conversation_id=conversation_id, role=str(role), content=content,
                status=status.value if hasattr(status, "value") else str(status),
            )
            conversation.updated_at = _now()
            session.add(row)
        return self._message(row)

    def update_message(self, message_id: str, **changes) -> Message:
        with self.sessions.begin() as session:
            row = session.get(MessageModel, message_id)
            if not row:
                raise ResourceNotFound("message not found")
            for field in ("content", "error_code", "error_message"):
                value = changes.get(field, UNSET)
                if value is not UNSET:
                    setattr(row, field, value)
            status = changes.get("status", UNSET)
            if status is not UNSET:
                row.status = status.value if hasattr(status, "value") else str(status)
            citations = changes.get("citations", UNSET)
            if citations is not UNSET:
                row.citations_json = json.dumps([asdict(item) for item in citations], ensure_ascii=False)
            warnings = changes.get("warnings", UNSET)
            if warnings is not UNSET:
                row.warnings_json = json.dumps(warnings, ensure_ascii=False)
        return self._message(row)

    def list_messages(self, conversation_id: str) -> list[Message]:
        with self.sessions() as session:
            rows = session.scalars(
                select(MessageModel).where(MessageModel.conversation_id == conversation_id)
                .order_by(MessageModel.created_at, MessageModel.id)
            )
            return [self._message(row) for row in rows]

    @staticmethod
    def _require(session: Session, conversation_id: str) -> ConversationModel:
        row = session.get(ConversationModel, conversation_id)
        if not row:
            raise ResourceNotFound("conversation not found")
        return row

    @staticmethod
    def _entity(row: ConversationModel) -> Conversation:
        return Conversation(
            row.id,
            row.title,
            ConversationStatus(row.status),
            row.created_at,
            row.updated_at,
            row.project_id,
        )

    @staticmethod
    def _message(row: MessageModel) -> Message:
        return Message(
            id=row.id, conversation_id=row.conversation_id, role=row.role, content=row.content,
            status=MessageStatus(row.status), error_code=row.error_code, error_message=row.error_message,
            citations=[Citation(**item) for item in json.loads(row.citations_json or "[]")],
            warnings=json.loads(row.warnings_json or "[]"), created_at=row.created_at,
        )


class SqliteDocumentRepository(RepositoryBase):
    def create(self, *, title, category, source_type, source_name, content_hash) -> KnowledgeDocument:
        with self.sessions.begin() as session:
            row = DocumentModel(id=_id(), title=title, category=category or "general", source_type=source_type,
                                source_name=source_name, content_hash=content_hash)
            session.add(row)
        return self._entity(row)

    def get(self, document_id: str) -> KnowledgeDocument | None:
        with self.sessions() as session:
            row = session.get(DocumentModel, document_id)
            return self._entity(row) if row else None

    def list(self, *, status=None, category=None, query=None, offset=0, limit=100) -> list[KnowledgeDocument]:
        with self.sessions() as session:
            statement = select(DocumentModel)
            if status:
                statement = statement.where(DocumentModel.status == (status.value if hasattr(status, "value") else status))
            if category:
                statement = statement.where(DocumentModel.category == category)
            if query:
                pattern = f"%{query}%"
                statement = statement.where(or_(DocumentModel.title.like(pattern), DocumentModel.source_name.like(pattern)))
            rows = session.scalars(statement.order_by(DocumentModel.updated_at.desc()).offset(offset).limit(limit))
            return [self._entity(row) for row in rows]

    def update(self, document_id: str, *, title=None, category=None) -> KnowledgeDocument:
        with self.sessions.begin() as session:
            row = self._require(session, document_id)
            if title is not None:
                row.title = title
            if category is not None:
                row.category = category
            row.updated_at = _now()
        return self._entity(row)

    def update_status(self, document_id: str, status: ResourceStatus, *, error_message=None) -> KnowledgeDocument:
        with self.sessions.begin() as session:
            row = self._require(session, document_id)
            row.status = status.value
            row.error_message = error_message
            row.updated_at = _now()
        return self._entity(row)

    def save_chunks(self, document_id: str, chunks: list[Chunk]) -> None:
        with self.sessions.begin() as session:
            self._require(session, document_id)
            old_ids = list(session.scalars(select(ChunkModel.id).where(ChunkModel.document_id == document_id)))
            self._remove_fts(session, old_ids)
            session.execute(delete(ChunkModel).where(ChunkModel.document_id == document_id))
            for chunk in chunks:
                session.add(_chunk_row(chunk))
                _insert_fts(session, chunk, ResourceType.KNOWLEDGE)

    def list_chunks(self, document_id: str) -> list[Chunk]:
        with self.sessions() as session:
            rows = session.scalars(select(ChunkModel).where(ChunkModel.document_id == document_id).order_by(ChunkModel.chunk_index))
            return [_chunk_entity(row) for row in rows]

    def delete(self, document_id: str) -> None:
        with self.sessions.begin() as session:
            row = self._require(session, document_id)
            ids = list(session.scalars(select(ChunkModel.id).where(ChunkModel.document_id == document_id)))
            self._remove_fts(session, ids)
            session.delete(row)

    @staticmethod
    def _remove_fts(session: Session, ids: list[str]) -> None:
        for chunk_id in ids:
            session.execute(text("DELETE FROM chunks_fts WHERE chunk_id=:id"), {"id": chunk_id})

    @staticmethod
    def _require(session: Session, document_id: str) -> DocumentModel:
        row = session.get(DocumentModel, document_id)
        if not row:
            raise ResourceNotFound("document not found")
        return row

    @staticmethod
    def _entity(row: DocumentModel) -> KnowledgeDocument:
        return KnowledgeDocument(row.id, row.title, row.category, row.source_type, row.source_name,
                                 row.content_hash, ResourceStatus(row.status), row.error_message,
                                 row.created_at, row.updated_at)


class SqliteMemoryRepository(RepositoryBase):
    def create(self, *, title, content, kind, source_type, source_conversation_id=None) -> Memory:
        with self.sessions.begin() as session:
            row = MemoryModel(id=_id(), title=title, content=content,
                              kind=kind.value if hasattr(kind, "value") else str(kind),
                              source_type=source_type, source_conversation_id=source_conversation_id)
            session.add(row)
        return self._entity(row)

    def get(self, memory_id: str) -> Memory | None:
        with self.sessions() as session:
            row = session.get(MemoryModel, memory_id)
            return self._entity(row) if row else None

    def list_confirmed(self, *, include_archived=False, offset=0, limit=100) -> list[Memory]:
        with self.sessions() as session:
            query = select(MemoryModel)
            if not include_archived:
                query = query.where(MemoryModel.status == "confirmed")
            return [self._entity(row) for row in session.scalars(query.order_by(MemoryModel.updated_at.desc()).offset(offset).limit(limit))]

    def update(self, memory_id: str, *, title=None, content=None, kind=None) -> Memory:
        with self.sessions.begin() as session:
            row = self._require(session, memory_id)
            if title is not None: row.title = title
            if content is not None: row.content = content
            if kind is not None: row.kind = kind.value if hasattr(kind, "value") else str(kind)
            row.updated_at = _now()
        return self._entity(row)

    def archive(self, memory_id: str) -> Memory:
        with self.sessions.begin() as session:
            row = self._require(session, memory_id)
            row.status = "archived"
            row.updated_at = _now()
        return self._entity(row)

    def delete(self, memory_id: str) -> None:
        with self.sessions.begin() as session:
            row = self._require(session, memory_id)
            ids = list(session.scalars(select(ChunkModel.id).where(ChunkModel.memory_id == memory_id)))
            for chunk_id in ids:
                session.execute(text("DELETE FROM chunks_fts WHERE chunk_id=:id"), {"id": chunk_id})
            session.delete(row)

    def create_candidate(self, *, title, content, kind, conversation_id=None, message_id=None) -> MemoryCandidate:
        with self.sessions.begin() as session:
            row = CandidateModel(id=_id(), proposed_title=title, proposed_content=content,
                                 kind=kind.value if hasattr(kind, "value") else str(kind),
                                 conversation_id=conversation_id, message_id=message_id)
            session.add(row)
        return self._candidate(row)

    def list_candidates(self, *, status=None, offset=0, limit=100) -> list[MemoryCandidate]:
        with self.sessions() as session:
            query = select(CandidateModel)
            if status:
                query = query.where(CandidateModel.status == (status.value if hasattr(status, "value") else status))
            return [self._candidate(row) for row in session.scalars(query.order_by(CandidateModel.created_at.desc()).offset(offset).limit(limit))]

    def get_candidate(self, candidate_id: str) -> MemoryCandidate | None:
        with self.sessions() as session:
            row = session.get(CandidateModel, candidate_id)
            return self._candidate(row) if row else None

    def update_candidate(self, candidate_id: str, *, title=None, content=None, kind=None) -> MemoryCandidate:
        with self.sessions.begin() as session:
            row = self._require_candidate(session, candidate_id)
            if title is not None: row.proposed_title = title
            if content is not None: row.proposed_content = content
            if kind is not None: row.kind = kind.value if hasattr(kind, "value") else str(kind)
        return self._candidate(row)

    def update_candidate_status(self, candidate_id: str, status: CandidateStatus) -> MemoryCandidate:
        with self.sessions.begin() as session:
            row = self._require_candidate(session, candidate_id)
            row.status = status.value
            row.reviewed_at = _now()
        return self._candidate(row)

    def save_chunks(self, memory_id: str, chunks: list[Chunk]) -> None:
        with self.sessions.begin() as session:
            self._require(session, memory_id)
            ids = list(session.scalars(select(ChunkModel.id).where(ChunkModel.memory_id == memory_id)))
            for chunk_id in ids:
                session.execute(text("DELETE FROM chunks_fts WHERE chunk_id=:id"), {"id": chunk_id})
            session.execute(delete(ChunkModel).where(ChunkModel.memory_id == memory_id))
            for chunk in chunks:
                session.add(_chunk_row(chunk))
                _insert_fts(session, chunk, ResourceType.MEMORY)

    def list_chunks(self, memory_id: str) -> list[Chunk]:
        with self.sessions() as session:
            return [_chunk_entity(row) for row in session.scalars(select(ChunkModel).where(ChunkModel.memory_id == memory_id).order_by(ChunkModel.chunk_index))]

    @staticmethod
    def _require(session: Session, memory_id: str) -> MemoryModel:
        row = session.get(MemoryModel, memory_id)
        if not row: raise ResourceNotFound("memory not found")
        return row

    @staticmethod
    def _require_candidate(session: Session, candidate_id: str) -> CandidateModel:
        row = session.get(CandidateModel, candidate_id)
        if not row: raise ResourceNotFound("memory candidate not found")
        return row

    @staticmethod
    def _entity(row: MemoryModel) -> Memory:
        return Memory(row.id, row.title, row.content, MemoryKind(row.kind), row.source_type,
                      row.source_conversation_id, MemoryStatus(row.status), row.created_at, row.updated_at)

    @staticmethod
    def _candidate(row: CandidateModel) -> MemoryCandidate:
        return MemoryCandidate(row.id, row.proposed_title, row.proposed_content, MemoryKind(row.kind),
                               row.conversation_id, row.message_id, CandidateStatus(row.status),
                               row.created_at, row.reviewed_at)


class SqliteMigrationRepository(RepositoryBase):
    def exists(self, namespace: str, vector_id: str) -> bool:
        with self.sessions() as session:
            return session.scalar(select(func.count()).select_from(MigrationRecordModel).where(
                MigrationRecordModel.namespace == namespace, MigrationRecordModel.vector_id == vector_id)) > 0

    def record(self, *, namespace, vector_id, target_type, target_id) -> None:
        with self.sessions.begin() as session:
            session.add(MigrationRecordModel(namespace=namespace, vector_id=vector_id,
                                             target_type=target_type.value, target_id=target_id))

    def count(self, *, namespace=None) -> int:
        with self.sessions() as session:
            query = select(func.count()).select_from(MigrationRecordModel)
            if namespace: query = query.where(MigrationRecordModel.namespace == namespace)
            return int(session.scalar(query) or 0)


def _chunk_row(chunk: Chunk) -> ChunkModel:
    return ChunkModel(id=chunk.id, document_id=chunk.document_id, memory_id=chunk.memory_id,
                      content=chunk.content, page_number=chunk.page_number, chunk_index=chunk.chunk_index,
                      token_count=chunk.token_count, vector_id=chunk.vector_id, namespace=chunk.namespace,
                      title=chunk.title, category=chunk.category)


def _chunk_entity(row: ChunkModel) -> Chunk:
    return Chunk(id=row.id, content=row.content, namespace=row.namespace, chunk_index=row.chunk_index,
                 document_id=row.document_id, memory_id=row.memory_id, page_number=row.page_number,
                 token_count=row.token_count, vector_id=row.vector_id, title=row.title,
                 category=row.category, created_at=row.created_at)


def _insert_fts(session: Session, chunk: Chunk, resource_type: ResourceType) -> None:
    session.execute(text("INSERT INTO chunks_fts(chunk_id,content,title,category,resource_type) "
                         "VALUES(:id,:content,:title,:category,:resource_type)"),
                    {"id": chunk.id, "content": chunk.content, "title": chunk.title or "",
                     "category": chunk.category or "", "resource_type": resource_type.value})


def _split_source(content: str, max_chars: int = 4000):
    lines = content.splitlines(keepends=True) or [content]
    output = []
    current: list[str] = []
    current_size = 0
    start_line = 1
    for line_number, line in enumerate(lines, start=1):
        if current and current_size + len(line) > max_chars:
            output.append(("".join(current), start_line, line_number - 1))
            current = []
            current_size = 0
            start_line = line_number
        if len(line) > max_chars:
            if current:
                output.append(("".join(current), start_line, line_number - 1))
                current = []
                current_size = 0
            for offset in range(0, len(line), max_chars):
                output.append((line[offset:offset + max_chars], line_number, line_number))
            start_line = line_number + 1
            continue
        current.append(line)
        current_size += len(line)
    if current:
        output.append(("".join(current), start_line, len(lines)))
    return output or [("", 1, 1)]


def _fts_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", query)
    return " OR ".join(f'"{item}"' for item in tokens[:12])
