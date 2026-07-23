from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.errors import InvalidStateTransition, ValidationError


class ResourceStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETING = "deleting"

    def can_transition_to(self, target: "ResourceStatus") -> bool:
        allowed = {
            ResourceStatus.PENDING: {ResourceStatus.INDEXING},
            ResourceStatus.INDEXING: {
                ResourceStatus.INDEXED,
                ResourceStatus.FAILED,
            },
            ResourceStatus.INDEXED: {
                ResourceStatus.INDEXING,
                ResourceStatus.DELETING,
            },
            ResourceStatus.FAILED: {
                ResourceStatus.INDEXING,
                ResourceStatus.DELETING,
            },
            ResourceStatus.DELETING: set(),
        }
        return target in allowed[self]

    def require_transition_to(self, target: "ResourceStatus") -> None:
        if not self.can_transition_to(target):
            raise InvalidStateTransition(
                f"cannot transition resource from {self.value} to {target.value}"
            )


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class MemoryStatus(StrEnum):
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class MemoryKind(StrEnum):
    PREFERENCE = "preference"
    FACT = "fact"
    DECISION = "decision"
    CONTEXT = "context"


class ResourceType(StrEnum):
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    PROJECT = "project"


@dataclass(frozen=True, slots=True)
class Citation:
    chunk_id: str
    title: str
    excerpt: str
    page_number: int | None = None
    category: str | None = None
    resource_type: str | None = None
    relative_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: MessageRole
    content: str


@dataclass(slots=True)
class ModelComparisonResult:
    model_id: str
    answer: str = ""
    error: str | None = None
    latency_ms: int = 0


@dataclass(slots=True)
class ModelProvider:
    id: str
    name: str
    provider_type: str
    base_url: str
    model_name: str
    secret_ref: str
    enabled: bool = True
    is_default: bool = False
    has_api_key: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Conversation:
    id: str
    title: str
    status: ConversationStatus = ConversationStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None
    project_id: str | None = None


@dataclass(slots=True)
class Project:
    id: str
    name: str
    root_path: str
    source_type: str = "local"
    source_uri: str | None = None
    status: str = "pending"
    source_revision: str | None = None
    tech_stack: list[str] = field(default_factory=list)
    last_scanned_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class ProjectFile:
    id: str
    project_id: str
    relative_path: str
    language: str
    content_hash: str
    content: str
    size_bytes: int = 0
    modified_ns: int = 0


@dataclass(slots=True)
class ProjectSymbol:
    id: str
    project_id: str
    project_file_id: str
    name: str
    kind: str
    line_number: int
    end_line_number: int | None = None


@dataclass(slots=True)
class ProjectRoute:
    id: str
    project_id: str
    project_file_id: str
    method: str
    path: str
    handler: str
    line_number: int


@dataclass(slots=True)
class ProjectRelation:
    id: str
    project_id: str
    source_path: str
    target: str
    kind: str
    inferred: bool = False


@dataclass(slots=True)
class ProjectScanSummary:
    project_id: str
    revision: str
    file_count: int
    symbol_count: int
    route_count: int
    relation_count: int
    skipped_count: int = 0


@dataclass(slots=True)
class ImprovementTask:
    id: str
    project_id: str
    title: str
    goal: str
    status: str = "planned"
    plan: dict = field(default_factory=dict)
    acceptance_criteria: list[str] = field(default_factory=list)
    completed_step_ids: list[str] = field(default_factory=list)
    agent_prompt: str = ""
    baseline_revision: str | None = None
    baseline_hashes: dict[str, str] = field(default_factory=dict)
    review: dict = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class ProjectChunk:
    id: str
    project_id: str
    project_file_id: str
    relative_path: str
    content: str
    start_line: int
    end_line: int
    vector_id: str | None = None


@dataclass(slots=True)
class AnalysisArtifact:
    id: str
    project_id: str
    artifact_type: str
    format: str
    content: str
    source_revision: str
    status: str = "ready"
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Message:
    id: str
    conversation_id: str
    role: str
    content: str
    status: MessageStatus = MessageStatus.PENDING
    error_code: str | None = None
    error_message: str | None = None
    citations: list[Citation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(slots=True)
class KnowledgeDocument:
    id: str
    title: str
    category: str
    source_type: str
    source_name: str
    content_hash: str
    status: ResourceStatus = ResourceStatus.PENDING
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Chunk:
    id: str
    content: str
    namespace: str
    chunk_index: int = 0
    document_id: str | None = None
    memory_id: str | None = None
    page_number: int | None = None
    token_count: int | None = None
    vector_id: str | None = None
    title: str | None = None
    category: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if (self.document_id is None) == (self.memory_id is None):
            raise ValidationError(
                "chunk must belong to exactly one document or memory"
            )


@dataclass(slots=True)
class Memory:
    id: str
    title: str
    content: str
    kind: MemoryKind
    source_type: str
    source_conversation_id: str | None = None
    status: MemoryStatus = MemoryStatus.CONFIRMED
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class MemoryCandidate:
    id: str
    proposed_title: str
    proposed_content: str
    kind: MemoryKind
    conversation_id: str | None = None
    message_id: str | None = None
    status: CandidateStatus = CandidateStatus.PENDING
    created_at: datetime | None = None
    reviewed_at: datetime | None = None


@dataclass(slots=True)
class ScoredChunk:
    chunk_id: str
    content: str
    score: float
    title: str | None = None
    category: str | None = None
    page_number: int | None = None
    resource_type: ResourceType = ResourceType.KNOWLEDGE
    document_id: str | None = None
    memory_id: str | None = None
    vector_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.document_id is not None and self.memory_id is not None:
            raise ValidationError("scored chunk cannot have multiple resource owners")
        if (
            self.document_id is not None
            and self.resource_type is not ResourceType.KNOWLEDGE
        ):
            raise ValidationError("document chunk must use the knowledge resource type")
        if (
            self.memory_id is not None
            and self.resource_type is not ResourceType.MEMORY
        ):
            raise ValidationError("memory chunk must use the memory resource type")


@dataclass(slots=True)
class RetrievalResult:
    documents: list[ScoredChunk] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IndexedChunk:
    vector_id: str
    values: list[float]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ComponentHealth:
    name: str
    ok: bool
    message: str | None = None
    details: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class MigrationSummary:
    scanned_vectors: int = 0
    created_chunks: int = 0
    skipped_vectors: int = 0
    failed_vectors: int = 0
    warnings: list[str] = field(default_factory=list)
