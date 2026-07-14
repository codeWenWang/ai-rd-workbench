from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import AppContainer
from app.domain.entities import Chunk, ComponentHealth, ResourceType
from app.infrastructure.retrieval.fts import SqliteFtsSearch
from app.main import create_app


class FakeModel:
    async def ainvoke(self, messages) -> str:
        return "离线测试回答"

    async def astream(self, messages) -> AsyncIterator[str]:
        yield "离线测试回答"


class FakeEmbeddings:
    async def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]

    async def embed_query(self, text):
        return [0.1, 0.2]


class FakeVectorIndex:
    def __init__(self):
        self.upserts = []

    async def upsert(self, namespace, chunks):
        self.upserts.extend(chunks)

    async def delete(self, namespace, vector_ids):
        return None

    async def query(self, namespace, vector, limit):
        return []

    async def list_ids(self, namespace):
        if False:
            yield ""

    async def fetch(self, namespace, vector_ids):
        return []

    async def health(self):
        return ComponentHealth("pinecone", True, details={"dimension": 2})


def make_container(tmp_path) -> AppContainer:
    settings = Settings(database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    container = AppContainer(settings)
    container.chat_model = FakeModel()
    container.embeddings = FakeEmbeddings()
    container.vector_index = FakeVectorIndex()
    return container


def test_liveness_and_chat_persist_without_network(tmp_path) -> None:
    client = TestClient(create_app(container=make_container(tmp_path)))
    assert client.get("/api/health/live").json() == {"status": "ok"}
    session_id = client.post("/api/chat/session").json()["session_id"]
    result = client.post("/api/chat", json={"session_id": session_id, "message": "你好"})
    assert result.status_code == 200
    assert result.json()["answer"] == "离线测试回答"
    messages = client.get(f"/api/conversations/{session_id}/messages").json()["items"]
    assert [item["role"] for item in messages] == ["user", "assistant"]


def test_stale_session_id_creates_a_replacement_conversation(tmp_path) -> None:
    client = TestClient(create_app(container=make_container(tmp_path)))

    result = client.post(
        "/api/chat",
        json={"session_id": "legacy-session-id", "message": "你好"},
    )

    assert result.status_code == 200
    assert result.json()["session_id"] != "legacy-session-id"


def test_first_message_generates_a_conversation_title(tmp_path) -> None:
    container = make_container(tmp_path)
    client = TestClient(create_app(container=container))
    session_id = client.post("/api/chat/session").json()["session_id"]

    result = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "排查 Pinecone 向量写入失败"},
    )

    assert result.status_code == 200
    conversation = next(
        item for item in client.get("/api/conversations").json()["items"]
        if item["id"] == session_id
    )
    assert conversation["title"] == "排查 Pinecone 向量写入失败"


def test_platform_docs_page_is_disabled(tmp_path) -> None:
    client = TestClient(create_app(container=make_container(tmp_path)))

    result = client.get("/docs")

    assert result.status_code == 404
    assert client.get("/openapi.json").status_code == 200


def test_stream_contract_emits_required_events(tmp_path) -> None:
    client = TestClient(create_app(container=make_container(tmp_path)))
    body = client.post("/api/chat/stream", json={"message": "你好"}).text
    for name in ("stage", "token", "citations", "done"):
        assert f"event: {name}" in body


def test_shared_fts_searches_persisted_chunks(tmp_path) -> None:
    container = make_container(tmp_path)
    document = container.documents.create(title="事务规范", category="backend", source_type="text",
                                          source_name="事务规范", content_hash="hash")
    container.documents.save_chunks(document.id, [Chunk(
        id="chunk-1", document_id=document.id, content="数据库事务必须保持一致性",
        namespace="rag", title=document.title, category=document.category,
    )])
    results = SqliteFtsSearch(container.database.session_factory).search("数据库事务", ResourceType.KNOWLEDGE, 5)
    assert results and results[0].chunk_id == "chunk-1"


def test_document_and_memory_management_flow(tmp_path) -> None:
    container = make_container(tmp_path)
    client = TestClient(create_app(container=container))
    created_document = client.post("/api/knowledge/text", json={
        "text": "事务边界应当清晰", "title": "研发规范", "category": "backend"
    })
    assert created_document.status_code == 200
    document_id = created_document.json()["document_id"]
    assert client.get("/api/documents").json()["items"][0]["status"] == "indexed"
    assert client.patch(f"/api/documents/{document_id}", json={"title": "后端规范"}).json()["title"] == "后端规范"

    created_memory = client.post("/api/memory/text", json={
        "text": "偏好 Python 3.11", "title": "技术偏好", "kind": "preference"
    })
    assert created_memory.status_code == 200
    memory_id = created_memory.json()["memory_id"]
    assert client.get(f"/api/memories/{memory_id}").json()["content"] == "偏好 Python 3.11"

    candidate = container.memory_use_case.create_candidate(
        title="格式偏好", content="偏好简洁回答", kind="preference"
    )
    confirmed = client.post(f"/api/memory-candidates/{candidate.id}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"


def test_duplicate_memory_reindexes_when_remote_vector_is_missing(tmp_path) -> None:
    container = make_container(tmp_path)
    client = TestClient(create_app(container=container))
    payload = {"text": "Prefer Python 3.11", "kind": "preference"}

    first = client.post("/api/memory/text", json=payload)
    assert first.status_code == 200
    container.vector_index.upserts.clear()

    second = client.post("/api/memory/text", json=payload)

    assert second.status_code == 200
    assert second.json()["memory_id"] == first.json()["memory_id"]
    assert container.vector_index.upserts


def test_memory_without_title_uses_chinese_default(tmp_path) -> None:
    client = TestClient(create_app(container=make_container(tmp_path)))

    result = client.post("/api/memory/text", json={"text": "偏好使用 Python 3.11"})

    assert result.status_code == 200
    assert result.json()["memory"]["title"] == "个人记忆"
