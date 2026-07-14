from dataclasses import fields

import pytest

from app.domain.entities import (
    CandidateStatus,
    Citation,
    Chunk,
    Conversation,
    ConversationStatus,
    IndexedChunk,
    MemoryKind,
    MemoryStatus,
    Message,
    MessageRole,
    MessageStatus,
    ModelMessage,
    ResourceStatus,
    ResourceType,
    RetrievalResult,
    ScoredChunk,
)
from app.domain.errors import InvalidStateTransition, ValidationError


def test_document_status_allows_failed_to_indexing_retry() -> None:
    assert ResourceStatus.FAILED.can_transition_to(ResourceStatus.INDEXING)


def test_document_status_rejects_indexed_to_pending() -> None:
    assert not ResourceStatus.INDEXED.can_transition_to(ResourceStatus.PENDING)


def test_document_status_transition_graph_is_exact() -> None:
    expected = {
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

    for current in ResourceStatus:
        actual = {
            target for target in ResourceStatus if current.can_transition_to(target)
        }
        assert actual == expected[current]


def test_invalid_document_status_transition_raises_stable_error() -> None:
    with pytest.raises(InvalidStateTransition) as exc_info:
        ResourceStatus.INDEXED.require_transition_to(ResourceStatus.PENDING)

    assert exc_info.value.code == "invalid_state_transition"
    assert "indexed" in str(exc_info.value)
    assert "pending" in str(exc_info.value)


def test_citation_exposes_pdf_page() -> None:
    citation = Citation(
        chunk_id="chunk-1",
        title="研发规范",
        excerpt="事务必须放在服务层",
        page_number=3,
        category="backend",
    )
    assert citation.page_number == 3


def test_domain_enums_expose_stable_wire_values() -> None:
    assert [status.value for status in MessageStatus] == [
        "pending",
        "completed",
        "failed",
    ]
    assert [status.value for status in MemoryStatus] == ["confirmed", "archived"]
    assert [status.value for status in CandidateStatus] == [
        "pending",
        "confirmed",
        "rejected",
    ]
    assert [kind.value for kind in MemoryKind] == [
        "preference",
        "fact",
        "decision",
        "context",
    ]
    assert [resource_type.value for resource_type in ResourceType] == [
        "knowledge",
        "memory",
        "project",
    ]


def test_model_message_roles_expose_stable_wire_values() -> None:
    assert [role.value for role in MessageRole] == [
        "system",
        "user",
        "assistant",
    ]


def test_model_message_is_an_immutable_slotted_value() -> None:
    message = ModelMessage(role=MessageRole.USER, content="Explain transactions")

    assert message.role is MessageRole.USER
    assert message.content == "Explain transactions"
    assert not hasattr(message, "__dict__")
    with pytest.raises(AttributeError):
        message.content = "mutated"  # type: ignore[misc]


def test_conversation_status_exposes_stable_wire_values_and_default() -> None:
    assert [status.value for status in ConversationStatus] == [
        "active",
        "archived",
    ]
    conversation = Conversation(id="conversation-1", title="New conversation")
    assert conversation.status is ConversationStatus.ACTIVE


def test_retrieval_results_do_not_share_mutable_defaults() -> None:
    first = RetrievalResult()
    second = RetrievalResult()

    first.documents.append(object())  # type: ignore[arg-type]
    first.warnings.append("semantic_retrieval_unavailable")

    assert second.documents == []
    assert second.warnings == []


def test_message_citations_and_warnings_do_not_share_mutable_defaults() -> None:
    first = Message(
        id="message-1",
        conversation_id="conversation-1",
        role="assistant",
        content="answer",
    )
    second = Message(
        id="message-2",
        conversation_id="conversation-1",
        role="assistant",
        content="another answer",
    )

    first.citations.append(
        Citation(chunk_id="chunk-1", title="title", excerpt="excerpt")
    )
    first.warnings.append("warning")

    assert second.citations == []
    assert second.warnings == []


def test_indexed_chunk_metadata_does_not_share_mutable_defaults() -> None:
    first = IndexedChunk(vector_id="vector-1", values=[0.1])
    second = IndexedChunk(vector_id="vector-2", values=[0.2])

    first.metadata["title"] = "secret-free title"

    assert second.metadata == {}


def test_required_domain_dataclasses_use_slots() -> None:
    assert "chunk_id" in {field.name for field in fields(Citation)}
    citation = Citation(chunk_id="chunk-1", title="title", excerpt="excerpt")
    assert not hasattr(citation, "__dict__")


@pytest.mark.parametrize(
    ("document_id", "memory_id"),
    [(None, None), ("document-1", "memory-1")],
)
def test_chunk_requires_exactly_one_resource_owner(
    document_id: str | None,
    memory_id: str | None,
) -> None:
    with pytest.raises(ValidationError):
        Chunk(
            id="chunk-1",
            content="content",
            namespace="rag",
            document_id=document_id,
            memory_id=memory_id,
        )


def test_scored_chunk_rejects_resource_type_that_conflicts_with_owner() -> None:
    with pytest.raises(ValidationError):
        ScoredChunk(
            chunk_id="chunk-1",
            content="content",
            score=0.9,
            memory_id="memory-1",
            resource_type=ResourceType.KNOWLEDGE,
        )
