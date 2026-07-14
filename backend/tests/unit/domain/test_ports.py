import inspect
from typing import Final, get_origin, get_type_hints

import app.domain.ports as ports_module
from app.domain.entities import MessageStatus, ModelMessage, ResourceType, ScoredChunk
from app.domain.ports import (
    ChatModel,
    ConversationRepository,
    DocumentRepository,
    EmbeddingModel,
    LexicalSearch,
    MemoryRepository,
    MigrationRepository,
    Retriever,
    UNSET,
    VectorIndex,
)


def test_repository_protocols_expose_required_operations() -> None:
    assert _public_methods(ConversationRepository) == {
        "add_message",
        "archive",
        "create",
        "delete",
        "get",
        "list",
        "list_messages",
        "rename",
        "update_message",
    }
    assert _public_methods(DocumentRepository) == {
        "create",
        "delete",
        "get",
        "list",
        "list_chunks",
        "save_chunks",
        "update_status",
    }
    assert _public_methods(MemoryRepository) == {
        "archive",
        "create",
        "create_candidate",
        "delete",
        "get",
        "get_candidate",
        "list_candidates",
        "list_chunks",
        "list_confirmed",
        "save_chunks",
        "update",
        "update_candidate",
        "update_candidate_status",
    }
    assert _public_methods(MigrationRepository) == {"count", "exists", "record"}
    assert _public_methods(LexicalSearch) == {"search"}


def test_external_protocols_expose_required_async_operations() -> None:
    assert _public_methods(ChatModel) == {"ainvoke", "astream"}
    assert _public_methods(EmbeddingModel) == {"embed_documents", "embed_query"}
    assert _public_methods(VectorIndex) == {
        "delete",
        "fetch",
        "health",
        "list_ids",
        "query",
        "upsert",
    }
    assert _public_methods(Retriever) == {"retrieve"}


def test_async_stream_protocols_return_iterators_directly() -> None:
    assert not inspect.iscoroutinefunction(ChatModel.astream)
    assert not inspect.iscoroutinefunction(VectorIndex.list_ids)


def test_chat_model_accepts_model_messages_not_persistence_messages() -> None:
    invoke_hints = get_type_hints(ChatModel.ainvoke)
    stream_hints = get_type_hints(ChatModel.astream)

    assert invoke_hints["messages"] == list[ModelMessage]
    assert stream_hints["messages"] == list[ModelMessage]
    assert invoke_hints["return"] is str


def test_lexical_search_owns_shared_knowledge_and_memory_fts() -> None:
    hints = get_type_hints(LexicalSearch.search)

    assert hints["query"] is str
    assert hints["resource_type"] is ResourceType
    assert hints["limit"] is int
    assert hints["return"] == list[ScoredChunk]


def test_message_updates_distinguish_omitted_fields_from_explicit_nulls() -> None:
    parameters = inspect.signature(
        ConversationRepository.update_message
    ).parameters

    assert parameters["content"].default is UNSET
    assert parameters["status"].default is UNSET
    assert parameters["error_code"].default is UNSET
    assert parameters["error_message"].default is UNSET
    assert parameters["citations"].default is UNSET
    assert parameters["warnings"].default is UNSET


def test_unset_is_a_final_singleton_with_a_private_type() -> None:
    module_hints = get_type_hints(ports_module, include_extras=True)

    assert not hasattr(ports_module, "UnsetType")
    assert type(UNSET).__name__ == "_UnsetType"
    assert get_origin(module_hints["UNSET"]) is Final
    assert repr(UNSET) == "UNSET"
    assert [
        value
        for value in vars(ports_module).values()
        if isinstance(value, type(UNSET))
    ] == [UNSET]


def test_repository_adds_messages_as_pending_by_default() -> None:
    parameters = inspect.signature(ConversationRepository.add_message).parameters

    assert parameters["status"].default is MessageStatus.PENDING


def _public_methods(protocol: type[object]) -> set[str]:
    return {
        name
        for name, value in vars(protocol).items()
        if callable(value) and not name.startswith("_")
    }
