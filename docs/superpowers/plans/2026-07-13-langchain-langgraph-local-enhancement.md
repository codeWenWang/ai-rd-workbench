# LangChain + LangGraph Local Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the current prototype as a local single-user knowledge workbench using LangGraph, LangChain, SQLite, Pinecone hybrid retrieval, verifiable citations, manageable memories/documents, and automated tests without requiring Redis.

**Architecture:** Keep FastAPI and the no-build frontend, but replace global service singletons with dependency-injected domain ports and infrastructure adapters. SQLite is the product source of truth and LangGraph checkpoint store; Pinecone is a derived vector index; SQLite FTS5 and Pinecone results are fused by a testable hybrid retriever.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2, SQLite/FTS5, LangChain, LangGraph, langgraph-checkpoint-sqlite, langchain-openai against DashScope, langchain-pinecone, Pinecone, pypdf, pytest, pytest-asyncio, pytest-cov, respx, HTML/CSS/JavaScript, Playwright.

---

## File Map

Create these focused modules before removing old services:

```text
backend/app/
  api/
    errors.py                 # Stable API error envelope and exception handlers
    chat_v2.py                # Conversation and streaming chat endpoints
    documents_v2.py           # Document CRUD and reindex endpoints
    memories_v2.py            # Memory and candidate review endpoints
    diagnostics.py            # Liveness, readiness, consistency status
  application/
    chat.py                   # Chat use case invokes compiled graph
    documents.py              # Ingestion/delete/reindex use cases
    memories.py               # Manual memory and candidate review use cases
    migration.py              # Idempotent Pinecone-to-SQLite import
  domain/
    entities.py               # Dataclasses/enums shared across layers
    errors.py                 # Domain exceptions
    ports.py                  # Repository/model/vector/retriever protocols
  infrastructure/
    db/
      base.py                 # SQLAlchemy engine/session/base
      models.py               # ORM tables and FTS table setup
      repositories.py         # Repository implementations
    documents/
      loaders.py              # Text/PDF loading with page metadata
      splitters.py            # Token-aware splitting
    llm/
      dashscope.py            # Lazy LangChain model and embeddings adapters
    retrieval/
      fts.py                  # SQLite FTS retriever
      hybrid.py               # RRF fusion and thresholds
    vectorstores/
      pinecone.py             # Pinecone adapter and health checks
  workflows/
    state.py                  # ChatGraphState
    nodes.py                  # Independently testable graph nodes
    chat_graph.py             # Graph assembly and conditional edges
  config.py                   # Expanded validated settings
  dependencies.py             # Cached lazy dependency providers
  main.py                     # App factory and router wiring
backend/tests/
  conftest.py
  unit/
  integration/
  api/
scripts/
  migrate_pinecone_to_sqlite.py
  check_index_consistency.py
frontend/js/
  api.js
  chat.js
  documents.js
  memories.js
  diagnostics.js
  app.js
```

Legacy modules remain available until their replacement task passes. Delete them only in Task 14.

---

### Task 1: Test Harness and Dependency Baseline

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/pytest.ini`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/unit/test_test_environment.py`

- [ ] **Step 1: Add a failing environment test**

```python
# backend/tests/unit/test_test_environment.py
def test_tests_block_live_network_by_default(live_network_enabled: bool) -> None:
    assert live_network_enabled is False
```

```python
# backend/tests/conftest.py
import os
import pytest


@pytest.fixture
def live_network_enabled() -> bool:
    return os.getenv("RUN_LIVE_TESTS") == "1"
```

- [ ] **Step 2: Run the test before installing test dependencies**

Run:

```powershell
cd E:\桌面\AI赋能平台\backend
.\.venv\Scripts\python.exe -m pytest tests/unit/test_test_environment.py -v
```

Expected: FAIL because `pytest` is not yet declared/installed in the project environment.

- [ ] **Step 3: Add runtime and development dependencies**

Replace the legacy LangChain/Pinecone declarations with this tested dependency set:

```text
# backend/requirements.txt additions
langchain==1.3.13
langgraph==1.2.9
langchain-openai==1.3.3
langchain-pinecone==0.2.13
langgraph-checkpoint-sqlite==3.1.0
sqlalchemy==2.0.51
aiosqlite==0.22.1
tiktoken==0.13.0
```

```text
# backend/requirements-dev.txt
-r requirements.txt
pytest==9.1.1
pytest-asyncio==1.4.0
pytest-cov==7.1.0
respx==0.23.1
playwright==1.61.0
pytest-playwright==0.8.0
```

Create:

```ini
# backend/pytest.ini
[pytest]
testpaths = tests
asyncio_mode = auto
markers =
    live: calls real DashScope or Pinecone services
addopts = -ra
```

- [ ] **Step 4: Install and verify the harness**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest tests/unit/test_test_environment.py -v
.\.venv\Scripts\python.exe -m pip check
```

Expected: one passing test and `No broken requirements found`.

- [ ] **Step 5: Record a checkpoint**

This workspace is not currently a Git repository. Record completion in this plan. If Git is initialized before execution, commit with:

```powershell
git add backend/requirements.txt backend/requirements-dev.txt backend/pytest.ini backend/tests
git commit -m "test: establish backend test harness"
```

---

### Task 2: Domain Types and Stable Error Contracts

**Files:**
- Create: `backend/app/domain/entities.py`
- Create: `backend/app/domain/errors.py`
- Create: `backend/app/domain/ports.py`
- Create: `backend/tests/unit/domain/test_entities.py`

- [ ] **Step 1: Write failing tests for state transitions and citations**

```python
from app.domain.entities import Citation, ResourceStatus
from app.domain.errors import InvalidStateTransition


def test_document_status_allows_failed_to_indexing_retry() -> None:
    assert ResourceStatus.FAILED.can_transition_to(ResourceStatus.INDEXING)


def test_document_status_rejects_indexed_to_pending() -> None:
    assert not ResourceStatus.INDEXED.can_transition_to(ResourceStatus.PENDING)


def test_citation_exposes_pdf_page() -> None:
    citation = Citation(
        chunk_id="chunk-1",
        title="研发规范",
        excerpt="事务必须放在服务层",
        page_number=3,
        category="backend",
    )
    assert citation.page_number == 3
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/domain/test_entities.py -v
```

Expected: import failure because domain modules do not exist.

- [ ] **Step 3: Implement minimal domain types**

```python
# backend/app/domain/entities.py
from dataclasses import dataclass
from enum import StrEnum


class ResourceStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETING = "deleting"

    def can_transition_to(self, target: "ResourceStatus") -> bool:
        allowed = {
            self.PENDING: {self.INDEXING},
            self.INDEXING: {self.INDEXED, self.FAILED},
            self.INDEXED: {self.INDEXING, self.DELETING},
            self.FAILED: {self.INDEXING, self.DELETING},
            self.DELETING: set(),
        }
        return target in allowed[self]


@dataclass(frozen=True, slots=True)
class Citation:
    chunk_id: str
    title: str
    excerpt: str
    page_number: int | None = None
    category: str | None = None
```

```python
# backend/app/domain/errors.py
class DomainError(Exception):
    code = "domain_error"


class InvalidStateTransition(DomainError):
    code = "invalid_state_transition"
```

Define protocols in `ports.py` for `ConversationRepository`, `DocumentRepository`, `MemoryRepository`, `VectorIndex`, `EmbeddingModel`, `ChatModel`, and `Retriever`. Each protocol method must use domain types rather than ORM models.

- [ ] **Step 4: Run domain tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/domain -v
```

Expected: all domain tests pass.

---

### Task 3: Validated Settings, App Factory, and Lazy Dependencies

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/dependencies.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/unit/test_config.py`
- Create: `backend/tests/api/test_liveness.py`

- [ ] **Step 1: Write failing tests proving liveness does not require Pinecone**

```python
from fastapi.testclient import TestClient
from app.main import create_app


def test_liveness_does_not_initialize_external_services(monkeypatch) -> None:
    monkeypatch.setenv("PINECONE_API_KEY", "invalid-but-unused")
    client = TestClient(create_app())
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Add config tests for SQLite URL, upload limits, graph timeout, retrieval candidates, and local CORS origins.

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_config.py tests/api/test_liveness.py -v
```

Expected: FAIL because `create_app` and new settings do not exist.

- [ ] **Step 3: Implement settings and app factory**

Add settings with explicit defaults:

```python
database_url: str = "sqlite:///./data/app.db"
max_upload_bytes: int = 20 * 1024 * 1024
max_pdf_pages: int = 300
chunk_size_tokens: int = 500
chunk_overlap_tokens: int = 80
retrieval_candidates: int = 20
retrieval_top_k: int = 6
graph_timeout_seconds: float = 60.0
cors_origins: list[str] = ["http://127.0.0.1:8000", "http://localhost:8000"]
langsmith_tracing: bool = False
```

Implement `create_app()` so routers and exception handlers are registered before the frontend mount. `GET /api/health/live` must not resolve model, database, or Pinecone providers.

Use `functools.lru_cache` provider functions in `dependencies.py`; do not instantiate external clients at module import.

- [ ] **Step 4: Verify liveness and configuration**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_config.py tests/api/test_liveness.py -v
```

Expected: all tests pass without network access.

---

### Task 4: SQLite Schema, FTS5, and Repositories

**Files:**
- Create: `backend/app/infrastructure/db/base.py`
- Create: `backend/app/infrastructure/db/models.py`
- Create: `backend/app/infrastructure/db/repositories.py`
- Create: `backend/app/infrastructure/db/schema.py`
- Create: `backend/tests/integration/db/test_repositories.py`
- Create: `backend/tests/integration/db/test_fts.py`

- [ ] **Step 1: Write failing repository tests**

```python
def test_conversation_messages_survive_new_session(conversation_repo) -> None:
    conversation = conversation_repo.create(title="测试会话")
    conversation_repo.add_message(conversation.id, role="user", content="你好")
    conversation_repo.session.close()
    messages = conversation_repo.list_messages(conversation.id)
    assert [message.content for message in messages] == ["你好"]


def test_fts_returns_matching_chunk(chunk_repo) -> None:
    chunk_repo.add_knowledge_chunk(
        chunk_id="c1",
        document_id="d1",
        content="Spring Boot 事务应放在 Service 层",
        title="研发规范",
        category="backend",
    )
    results = chunk_repo.fts_search("Spring Boot 事务", limit=10)
    assert [item.id for item in results] == ["c1"]
```

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/db -v
```

Expected: FAIL because schema and repositories do not exist.

- [ ] **Step 3: Implement schema and repositories**

Create SQLAlchemy 2 models for all tables in the design spec. Store assistant citations and graph warnings in `messages.citations_json` and `messages.warnings_json` JSON text columns so restored conversations retain source details. Create FTS5 explicitly:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    chunk_id UNINDEXED,
    content,
    title,
    category,
    tokenize='unicode61'
);
```

Repository writes must update the FTS table in the same transaction as chunk changes. Tests use a temporary on-disk SQLite database, not `:memory:`, so multiple sessions see the same data.

- [ ] **Step 4: Verify repositories and FTS**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/db -v
```

Expected: CRUD persistence and FTS tests pass.

---

### Task 5: DashScope LangChain Adapters

**Files:**
- Create: `backend/app/infrastructure/llm/dashscope.py`
- Create: `backend/tests/unit/infrastructure/test_dashscope_adapters.py`
- Modify: `backend/app/dependencies.py`

- [ ] **Step 1: Write failing adapter tests**

```python
def test_chat_model_uses_dashscope_compatible_endpoint(settings) -> None:
    adapter = DashScopeChatModel(settings)
    client = adapter.build_client()
    assert str(client.openai_api_base).rstrip("/") == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def test_embedding_adapter_requests_configured_dimensions(settings) -> None:
    adapter = DashScopeEmbeddings(settings)
    assert adapter.dimensions == 1024
```

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/infrastructure/test_dashscope_adapters.py -v
```

- [ ] **Step 3: Implement lazy LangChain adapters**

Build `ChatOpenAI` and `OpenAIEmbeddings` with the configured DashScope base URL, API key, model names, dimensions, explicit request timeout, and bounded retries. Construction must not make a network call.

Expose only `invoke/ainvoke/astream` and `embed_documents/embed_query` behavior required by domain ports.

- [ ] **Step 4: Verify without live network**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/infrastructure/test_dashscope_adapters.py -v
```

Expected: tests pass without calling DashScope.

---

### Task 6: Document Loading, Token Splitting, and Validation

**Files:**
- Create: `backend/app/infrastructure/documents/loaders.py`
- Create: `backend/app/infrastructure/documents/splitters.py`
- Create: `backend/tests/unit/documents/test_loaders.py`
- Create: `backend/tests/unit/documents/test_splitters.py`

- [ ] **Step 1: Write failing tests**

```python
def test_pdf_loader_keeps_one_based_page_numbers(sample_pdf_bytes) -> None:
    documents = load_pdf(sample_pdf_bytes, filename="guide.pdf", max_pages=10)
    assert [doc.metadata["page_number"] for doc in documents] == [1, 2]


def test_splitter_preserves_source_metadata() -> None:
    source = Document(
        page_content="事务管理。" * 1000,
        metadata={"source": "guide.pdf", "page_number": 2},
    )
    chunks = split_documents([source], chunk_size=200, overlap=30)
    assert len(chunks) > 1
    assert all(chunk.metadata["page_number"] == 2 for chunk in chunks)
```

Also test bad PDF header, empty extracted text, maximum page count, maximum bytes, and overlap smaller than chunk size.

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/documents -v
```

- [ ] **Step 3: Implement loaders and splitters**

Return LangChain `Document` instances. Use `RecursiveCharacterTextSplitter.from_tiktoken_encoder` with Chinese punctuation separators. Assign each output chunk stable metadata: source, page_number, chunk_index, token_count.

- [ ] **Step 4: Verify**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/documents -v
```

Expected: validation and metadata preservation tests pass.

---

### Task 7: Pinecone Adapter and Reliable Ingestion Use Case

**Files:**
- Create: `backend/app/infrastructure/vectorstores/pinecone.py`
- Create: `backend/app/application/documents.py`
- Create: `backend/tests/unit/application/test_document_ingestion.py`
- Create: `backend/tests/unit/infrastructure/test_pinecone_adapter.py`

- [ ] **Step 1: Write a failing ingestion state test**

```python
async def test_embedding_failure_marks_document_failed(
    document_repo, fake_loader, failing_embeddings, fake_vector_index
) -> None:
    use_case = DocumentUseCase(
        repository=document_repo,
        loader=fake_loader,
        embeddings=failing_embeddings,
        vector_index=fake_vector_index,
    )
    document = await use_case.ingest_text("内容", title="标题", category="general")
    stored = document_repo.get(document.id)
    assert stored.status == ResourceStatus.FAILED
    assert stored.error_message == "embedding unavailable"
```

Add success, retry, reindex, delete, duplicate hash, and partial vector failure tests.

Add a Chinese retrieval test using the sentence `Spring Boot 事务应放在 Service 层`. If the Unicode tokenizer cannot retrieve it with the query `事务 Service`, add a `search_text` column populated by `jieba.cut_for_search`; keep `jieba` only when this test proves it is needed.

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/application/test_document_ingestion.py -v
```

- [ ] **Step 3: Implement Pinecone adapter and use case**

The adapter must support:

```python
async def upsert(self, namespace: str, chunks: list[IndexedChunk]) -> None: ...
async def delete(self, namespace: str, vector_ids: list[str]) -> None: ...
async def query(self, namespace: str, vector: list[float], limit: int) -> list[ScoredChunk]: ...
async def list_ids(self, namespace: str) -> AsyncIterator[str]: ...
async def fetch(self, namespace: str, vector_ids: list[str]) -> list[IndexedChunk]: ...
async def health(self) -> ComponentHealth: ...
```

`DocumentUseCase` must persist state changes before and after external calls. Preserve failed rows for retry.

- [ ] **Step 4: Verify ingestion behavior**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/application/test_document_ingestion.py tests/unit/infrastructure/test_pinecone_adapter.py -v
```

---

### Task 8: FTS + Pinecone Hybrid Retriever

**Files:**
- Create: `backend/app/infrastructure/retrieval/fts.py`
- Create: `backend/app/infrastructure/retrieval/hybrid.py`
- Create: `backend/tests/unit/retrieval/test_rrf.py`
- Create: `backend/tests/integration/retrieval/test_hybrid_retriever.py`

- [ ] **Step 1: Write failing RRF and degradation tests**

```python
def test_rrf_rewards_documents_returned_by_both_retrievers() -> None:
    dense = [scored("a", 0.9), scored("b", 0.8)]
    lexical = [scored("b", 12.0), scored("c", 10.0)]
    result = reciprocal_rank_fusion(dense, lexical, limit=3)
    assert result[0].chunk_id == "b"


async def test_pinecone_failure_returns_fts_results_with_warning(
    fts_retriever, failing_vector_retriever
) -> None:
    retriever = HybridRetriever(fts_retriever, failing_vector_retriever)
    result = await retriever.retrieve("事务", resource_type="knowledge")
    assert result.documents
    assert result.warnings == ["semantic_retrieval_unavailable"]
```

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/retrieval tests/integration/retrieval -v
```

- [ ] **Step 3: Implement retrievers**

Normalize outputs to a shared `ScoredChunk`. Fuse by rank, not raw score. Apply a configurable minimum relevance rule and cap knowledge and memory results separately before returning at most six documents.

- [ ] **Step 4: Verify deterministic ranking**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/retrieval tests/integration/retrieval -v
```

Expected: duplicate chunks are removed, shared results rank first, Pinecone failure degrades cleanly.

---

### Task 9: Memory CRUD and Candidate Confirmation

**Files:**
- Create: `backend/app/application/memories.py`
- Create: `backend/tests/unit/application/test_memories.py`

- [ ] **Step 1: Write failing confirmation tests**

```python
async def test_candidate_does_not_enter_retrieval_before_confirmation(
    memory_use_case, memory_repo, vector_index
) -> None:
    candidate = memory_repo.create_candidate(
        title="技术偏好", content="偏好 Python 3.11", kind="preference"
    )
    assert memory_repo.list_confirmed() == []
    assert vector_index.upserts == []

    memory = await memory_use_case.confirm_candidate(candidate.id)

    assert memory.content == "偏好 Python 3.11"
    assert len(vector_index.upserts) == 1
```

Also test edit-before-confirm, reject, duplicate confirmed memory, update/reindex, delete, manual text memory ingestion, and PDF memory ingestion with preserved page numbers.

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/application/test_memories.py -v
```

- [ ] **Step 3: Implement memory use case**

Confirmed memory is global to the local user and never filtered by conversation ID. Preserve `source_conversation_id` only for traceability.

- [ ] **Step 4: Verify memory behavior**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/application/test_memories.py -v
```

---

### Task 10: LangGraph State, Nodes, and Bounded Workflow

**Files:**
- Create: `backend/app/workflows/state.py`
- Create: `backend/app/workflows/nodes.py`
- Create: `backend/app/workflows/chat_graph.py`
- Create: `backend/tests/unit/workflows/test_chat_graph.py`

- [ ] **Step 1: Write failing graph path tests**

```python
async def test_graph_retries_retrieval_only_once(graph_factory) -> None:
    graph, fakes = graph_factory(context_sufficient=[False, False])
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "未知问题"}], "retry_count": 0},
        {"configurable": {"thread_id": "thread-1"}},
    )
    assert fakes.retriever.call_count == 2
    assert result["retry_count"] == 1
    assert result["citations"] == []


async def test_graph_creates_candidate_but_not_confirmed_memory(graph_factory) -> None:
    graph, fakes = graph_factory(memory_candidate="偏好 Python 3.11")
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "我偏好 Python 3.11"}]},
        {"configurable": {"thread_id": "thread-2"}},
    )
    assert result["memory_candidates"]
    assert fakes.vector_index.memory_upserts == []
```

Test sufficient context, one retry then success, no-context answer, Pinecone warning propagation, model failure, citation filtering, and message persistence.

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/workflows/test_chat_graph.py -v
```

- [ ] **Step 3: Implement state and graph**

Define `ChatGraphState` as a `TypedDict` with the fields in the approved design. Assemble nodes:

```text
START -> receive_query -> understand_query -> retrieve_context
retrieve_context -> merge_and_rank -> evaluate_context
evaluate_context --sufficient--> generate_answer
evaluate_context --retry--> rewrite_query -> retrieve_context
evaluate_context --exhausted--> generate_insufficient_answer
generate_answer -> validate_citations -> persist_result -> propose_memories -> END
generate_insufficient_answer -> persist_result -> propose_memories -> END
```

Compile with `AsyncSqliteSaver`. Every conditional route must be a pure function covered by tests.

- [ ] **Step 4: Verify the full graph suite**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/workflows/test_chat_graph.py -v
```

---

### Task 11: Conversation API, SSE, and Error Envelope

**Files:**
- Create: `backend/app/api/errors.py`
- Create: `backend/app/api/chat_v2.py`
- Create: `backend/app/application/chat.py`
- Create: `backend/tests/api/test_chat_api.py`
- Create: `backend/tests/api/test_chat_stream.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_create_conversation_and_restore_messages(client) -> None:
    created = client.post("/api/chat/session").json()
    conversation_id = created["session_id"]
    client.post("/api/chat", json={"session_id": conversation_id, "message": "你好"})
    response = client.get(f"/api/conversations/{conversation_id}/messages")
    assert [m["role"] for m in response.json()["items"]] == ["user", "assistant"]


def test_stream_emits_stage_token_citation_and_done_events(client) -> None:
    with client.stream(
        "POST", "/api/chat/stream", json={"message": "解释事务", "session_id": None}
    ) as response:
        body = "".join(response.iter_text())
    assert "event: stage" in body
    assert "event: token" in body
    assert "event: citations" in body
    assert "event: done" in body
```

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_chat_api.py tests/api/test_chat_stream.py -v
```

- [ ] **Step 3: Implement APIs and errors**

Use stable error JSON:

```json
{
  "code": "model_unavailable",
  "message": "模型服务暂不可用，请稍后重试",
  "request_id": "...",
  "details": null
}
```

SSE event names are `stage`, `token`, `citations`, `warning`, `error`, and `done`. Preserve `POST /api/chat` as the non-streaming compatibility path.

- [ ] **Step 4: Verify API behavior**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_chat_api.py tests/api/test_chat_stream.py -v
```

---

### Task 12: Document, Memory, and Diagnostics APIs

**Files:**
- Create: `backend/app/api/documents_v2.py`
- Create: `backend/app/api/memories_v2.py`
- Create: `backend/app/api/diagnostics.py`
- Create: `backend/tests/api/test_documents_api.py`
- Create: `backend/tests/api/test_memories_api.py`
- Create: `backend/tests/api/test_diagnostics_api.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing CRUD and readiness tests**

```python
def test_document_list_exposes_indexing_status(client) -> None:
    response = client.get("/api/documents?status=failed")
    assert response.status_code == 200
    assert all(item["status"] == "failed" for item in response.json()["items"])


def test_confirm_memory_candidate(client, seeded_candidate) -> None:
    response = client.post(f"/api/memory-candidates/{seeded_candidate.id}/confirm")
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_readiness_reports_component_failure_without_500(client, fake_health) -> None:
    fake_health.pinecone_ok = False
    response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json()["components"]["pinecone"]["status"] == "error"
```

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_documents_api.py tests/api/test_memories_api.py tests/api/test_diagnostics_api.py -v
```

- [ ] **Step 3: Implement management APIs**

Add pagination, search, category/status filters, details, edit, delete, reindex, candidate confirm/reject, liveness/readiness, namespace counts, and consistency summary. Keep legacy knowledge and memory ingestion paths as aliases calling the new use cases. `/api/memory/pdf` loads and splits the PDF through the same document pipeline, creates one confirmed memory resource with multiple chunks, and ignores the legacy `session_id` for retrieval isolation while preserving it as migration/source metadata.

- [ ] **Step 4: Verify management APIs**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_documents_api.py tests/api/test_memories_api.py tests/api/test_diagnostics_api.py -v
```

---

### Task 13: Idempotent Existing-Data Migration

**Files:**
- Create: `backend/app/application/migration.py`
- Create: `scripts/migrate_pinecone_to_sqlite.py`
- Create: `scripts/check_index_consistency.py`
- Create: `backend/tests/unit/application/test_migration.py`

- [ ] **Step 1: Write failing migration tests**

```python
async def test_migration_is_idempotent(migration_use_case, fake_pinecone, repositories) -> None:
    fake_pinecone.seed("rag", vector_id="v1", metadata={"title": "规范", "text": "内容"})
    first = await migration_use_case.run(dry_run=False)
    second = await migration_use_case.run(dry_run=False)
    assert first.created_chunks == 1
    assert second.created_chunks == 0
    assert repositories.migrations.count() == 1


async def test_dry_run_does_not_write(migration_use_case, repositories) -> None:
    result = await migration_use_case.run(dry_run=True)
    assert result.scanned_vectors >= 0
    assert repositories.migrations.count() == 0
```

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/application/test_migration.py -v
```

- [ ] **Step 3: Implement migration and consistency scripts**

CLI behavior:

```powershell
python scripts/migrate_pinecone_to_sqlite.py --dry-run
python scripts/migrate_pinecone_to_sqlite.py --backup-db
python scripts/check_index_consistency.py
```

Migration enumerates `rag` and `ltm`, fetches metadata in batches, preserves vector IDs, groups `rag` by title/category/source type, imports `ltm` as confirmed memories, and records namespace + vector ID uniqueness. It must not delete or update Pinecone vectors.

- [ ] **Step 4: Verify with Fake, then optional live dry-run**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/application/test_migration.py -v
$env:RUN_LIVE_TESTS='1'
.\.venv\Scripts\python.exe ..\scripts\migrate_pinecone_to_sqlite.py --dry-run
Remove-Item Env:RUN_LIVE_TESTS
```

Expected live dry-run for the current environment: scan four existing vectors and write zero SQLite records.

---

### Task 14: Frontend Workbench and Browser Tests

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/css/style.css`
- Modify: `frontend/js/app.js`
- Create: `frontend/js/api.js`
- Create: `frontend/js/chat.js`
- Create: `frontend/js/documents.js`
- Create: `frontend/js/memories.js`
- Create: `frontend/js/diagnostics.js`
- Create: `backend/tests/e2e/test_workbench.py`

- [ ] **Step 1: Write failing browser tests for core workflows**

```python
def test_chat_restores_conversation_and_opens_citation(page, live_server) -> None:
    page.goto(live_server.url)
    page.get_by_role("button", name="新建会话").click()
    page.get_by_placeholder("输入问题").fill("解释事务管理")
    page.get_by_role("button", name="发送").click()
    page.get_by_role("button", name="查看引用 1").click()
    assert page.get_by_text("原文片段").is_visible()
    page.reload()
    assert page.get_by_text("解释事务管理").is_visible()


def test_memory_candidate_can_be_edited_and_confirmed(page, live_server) -> None:
    page.goto(f"{live_server.url}/#memories")
    page.get_by_role("tab", name="待确认").click()
    page.get_by_role("button", name="编辑").first.click()
    page.get_by_label("记忆内容").fill("偏好 Python 3.11")
    page.get_by_role("button", name="确认保存").click()
    assert page.get_by_text("偏好 Python 3.11").is_visible()
```

- [ ] **Step 2: Verify RED**

Run after Task 1 installs Playwright and Chromium:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/e2e/test_workbench.py -v
```

Expected: FAIL because the new UI controls do not exist.

- [ ] **Step 3: Implement the no-build modular frontend**

Build four views: conversations/chat, documents, memories/candidates, diagnostics. Use `<script type="module">`. Implement an API wrapper that parses the stable error envelope and an SSE parser that handles stage/token/citations/warning/error/done events.

Use tables for document and memory management, dialogs for editing/deletion, and a side panel for citations. Keep cards only for repeated diagnostics items. Ensure controls have stable dimensions and no nested cards.

- [ ] **Step 4: Verify desktop and mobile workflows**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/e2e/test_workbench.py -v
```

Capture screenshots at 1440x900 and 390x844. Verify no overlapping text, blank panels, horizontal overflow, or unusable controls.

---

### Task 15: Remove Legacy Redis/BM25 Path and Update Startup

**Files:**
- Delete after replacement tests pass: `backend/app/services/short_term_memory.py`
- Delete after replacement tests pass: `backend/app/services/pinecone_store.py`
- Delete after replacement tests pass: `backend/app/services/rag_service.py`
- Delete after replacement tests pass: `backend/app/services/long_term_memory.py`
- Delete after replacement tests pass: `backend/app/services/chat_service.py`
- Delete after replacement tests pass: `backend/app/services/llm_service.py`
- Delete after replacement tests pass: `backend/app/services/embedding_service.py`
- Delete after replacement tests pass: `backend/app/services/openai_client.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`
- Modify: `start.bat`
- Modify: `研发文档.md`
- Modify: `.gitignore`
- Create: `backend/tests/api/test_no_redis_dependency.py`

- [ ] **Step 1: Write a failing no-Redis startup test**

```python
def test_application_imports_without_redis_installed(monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "redis", None)
    from app.main import create_app
    app = create_app()
    assert app.title
```

- [ ] **Step 2: Verify RED while legacy imports remain**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_no_redis_dependency.py -v
```

Expected: FAIL if any active router or dependency imports Redis-backed legacy services.

- [ ] **Step 3: Remove obsolete code and dependencies**

Remove `redis` and `rank-bm25` from runtime requirements. Keep `jieba` only if the FTS Chinese benchmark added during Task 8 proves it materially improves retrieval.

Change `start.bat` so it does not run `pip install` on every launch and fails clearly when `.venv` is missing:

```bat
@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment missing. Run: py -3.11 -m venv .venv
    exit /b 1
)
call .venv\Scripts\activate.bat
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Add `backend/data/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, and `.superpowers/` to `.gitignore`.

- [ ] **Step 4: Verify no-Redis operation**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_no_redis_dependency.py -v
.\.venv\Scripts\python.exe -m pip check
```

---

### Task 16: Full Verification, Live Migration, and Documentation

**Files:**
- Modify only the concrete implementation or test file named by a failing verification command from Tasks 1-15; do not perform unrelated cleanup
- Create: `backend/tests/live/test_live_services.py`
- Update: `研发文档.md`

- [ ] **Step 1: Run the complete offline suite**

```powershell
cd E:\桌面\AI赋能平台\backend
.\.venv\Scripts\python.exe -m pytest -m "not live" --cov=app --cov-report=term-missing --cov-report=html
```

Expected: zero failures; core domain/application/workflow coverage at or above 80%.

- [ ] **Step 2: Run static and dependency checks**

```powershell
.\.venv\Scripts\python.exe -m compileall -q app
.\.venv\Scripts\python.exe -m pip check
```

Expected: both commands exit 0.

- [ ] **Step 3: Verify live services explicitly**

```powershell
$env:RUN_LIVE_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/live -m live -v
Remove-Item Env:RUN_LIVE_TESTS
```

Tests check Redis is not required, SQLite is writable, Pinecone index dimension is 1024, embedding returns 1024 values, and a minimal model completion succeeds.

- [ ] **Step 4: Execute migration with backup**

```powershell
.\.venv\Scripts\python.exe ..\scripts\migrate_pinecone_to_sqlite.py --dry-run
.\.venv\Scripts\python.exe ..\scripts\migrate_pinecone_to_sqlite.py --backup-db
.\.venv\Scripts\python.exe ..\scripts\check_index_consistency.py
```

Expected for the current project data: four existing Pinecone vectors represented in SQLite, zero duplicate migration records, and no orphaned vector IDs.

- [ ] **Step 5: Start and manually verify the workbench**

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify:

```text
GET /api/health/live returns 200
GET /api/health/ready returns component details
The root page loads without a second frontend server
Chat streams stages, tokens, citations, and completion
Conversations survive refresh
Documents can be viewed, reindexed, and deleted
Memory candidates do not affect retrieval until confirmed
Pinecone failure displays a semantic-search degradation warning
```

- [ ] **Step 6: Update documentation and record final checkpoint**

Document environment creation, dependency installation, startup, SQLite location, migration, diagnostics, tests, optional LangSmith setup, and key rotation. If Git has been initialized, commit the verified result:

```powershell
git add .
git commit -m "feat: rebuild knowledge workbench with LangGraph"
```

---

## Implementation Order and Stop Conditions

Execute tasks strictly in order. Do not delete legacy services until Tasks 1-14 pass. Stop and investigate before continuing when:

- A new test fails for a reason different from the intended missing behavior.
- A default test attempts real network access.
- SQLite and Pinecone cannot be reconciled after a failed write.
- The Graph exceeds one retrieval retry.
- Migration dry-run reports missing metadata that prevents a safe target mapping.
- Browser verification shows overlapping or inaccessible controls.

The implementation is complete only after Task 16 produces fresh verification evidence.
