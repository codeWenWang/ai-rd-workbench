from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import AppContainer
from app.main import create_app
from app.infrastructure.llm.gateway import ModelGateway


class FakeEmbeddings:
    async def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]

    async def embed_query(self, text):
        return [0.1, 0.2]


class FakeVectorIndex:
    def __init__(self):
        self.upserts = []

    async def upsert(self, namespace, chunks):
        self.upserts.append((namespace, chunks))

    async def delete(self, namespace, vector_ids):
        return None

    async def query(self, namespace, vector, limit):
        return []

    async def list_ids(self, namespace):
        if False:
            yield ""

    async def fetch(self, namespace, vector_ids):
        return []


class FixedModel:
    def __init__(self, answer):
        self.answer = answer

    async def ainvoke(self, messages):
        return self.answer

    async def astream(self, messages):
        yield self.answer


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        dashscope_api_key="test-dashscope-key",
        pinecone_api_key="test-pinecone-key",
    )
    container = AppContainer(settings)
    container.embeddings = FakeEmbeddings()
    container.vector_index = FakeVectorIndex()
    return TestClient(create_app(container=container))


def test_project_scan_artifacts_and_conversation_filter_flow(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        "from fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef health(): return {'ok': True}\n",
        encoding="utf-8",
    )
    client = make_client(tmp_path)

    created = client.post("/api/projects", json={"name": "demo", "root_path": str(source)})
    assert created.status_code == 200
    project_id = created.json()["id"]

    scanned = client.post(f"/api/projects/{project_id}/scan")
    assert scanned.status_code == 200
    assert scanned.json()["file_count"] == 1
    assert scanned.json()["indexed_chunks"] == 1

    files = client.get(f"/api/projects/{project_id}/files").json()["items"]
    assert files[0]["relative_path"] == "main.py"

    artifact = client.post(f"/api/projects/{project_id}/artifacts/architecture")
    assert artifact.status_code == 200
    assert artifact.json()["format"] == "mermaid"

    session = client.post("/api/chat/session", json={"project_id": project_id}).json()
    conversations = client.get("/api/conversations", params={"project_id": project_id}).json()
    assert conversations["items"][0]["id"] == session["session_id"]


def test_model_provider_api_hides_secret_and_platform_docs_are_removed(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    provider = client.post("/api/model-providers", json={
        "name": "OpenAI Compatible",
        "provider_type": "openai_compatible",
        "base_url": "https://example.test/v1",
        "model_name": "example-chat",
        "api_key": "sk-super-secret",
    })

    assert provider.status_code == 200
    assert provider.json()["has_api_key"] is True
    assert "api_key" not in provider.json()
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 200


def test_model_comparison_api_returns_two_independent_answers(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    container = client.app.state.container
    container.model_gateway = ModelGateway({"a": FixedModel("回答 A"), "b": FixedModel("回答 B")})
    container.__dict__.pop("chat_use_case", None)

    result = client.post("/api/models/compare", json={
        "message": "比较模型",
        "model_ids": ["a", "b"],
    })

    assert result.status_code == 200
    assert [item["answer"] for item in result.json()["items"]] == ["回答 A", "回答 B"]
