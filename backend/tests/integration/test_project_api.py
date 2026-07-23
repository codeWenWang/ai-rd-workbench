import asyncio
from pathlib import Path
import shutil
import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import AppContainer
from app.main import create_app
from app.infrastructure.llm.gateway import ModelGateway
from app.infrastructure.projects.remote_git import (
    RemoteRepository,
    normalize_repository_url,
)


class FakeEmbeddings:
    async def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]

    async def embed_query(self, text):
        return [0.1, 0.2]


class FakeVectorIndex:
    def __init__(self):
        self.upserts = []
        self.deletes = []

    async def upsert(self, namespace, chunks):
        self.upserts.append((namespace, chunks))

    async def delete(self, namespace, vector_ids):
        self.deletes.append((namespace, vector_ids))

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


class PromptEchoModel:
    async def ainvoke(self, messages):
        return messages[0].content

    async def astream(self, messages):
        yield messages[0].content


class UnavailableEmbeddings:
    async def embed_documents(self, texts):
        raise RuntimeError("embedding service unavailable")

    async def embed_query(self, text):
        raise RuntimeError("embedding service unavailable")


class SlowProjectIndexer:
    async def index(self, project_id):
        await asyncio.sleep(0.3)
        return 1


class FakeRemoteGit:
    def __init__(self, cache_root: Path, warnings=None):
        self.cache_root = cache_root
        self.warnings = list(warnings or [])

    def clone(self, url: str, *, expected_source: str | None = None):
        remote = normalize_repository_url(url, expected_source)
        target = self.cache_root / f"{remote.source_type}-{remote.name}"
        target.mkdir(parents=True, exist_ok=True)
        (target / ".git").mkdir(exist_ok=True)
        (target / "main.py").write_text(
            "from fastapi import FastAPI\napp=FastAPI()\n@app.get('/remote')\ndef remote(): return {}\n",
            encoding="utf-8",
        )
        return RemoteRepository(
            source_type=remote.source_type,
            url=remote.url,
            owner=remote.owner,
            name=remote.name,
            cache_path=target.resolve(),
        )

    def update(self, cache_path):
        return list(self.warnings)

    def remove(self, cache_path):
        shutil.rmtree(cache_path)


def make_client(tmp_path: Path, *, remote_warnings=None) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        dashscope_api_key="test-dashscope-key",
        pinecone_api_key="test-pinecone-key",
        git_cache_dir=str(tmp_path / "git-cache"),
    )
    container = AppContainer(settings)
    container.remote_git = FakeRemoteGit(
        tmp_path / "git-cache",
        warnings=remote_warnings,
    )
    container.embeddings = FakeEmbeddings()
    container.vector_index = FakeVectorIndex()
    return TestClient(create_app(container=container))


def test_project_api_accepts_public_github_and_gitee_repositories(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    github = client.post("/api/projects", json={
        "name": "GitHub demo",
        "source_type": "github",
        "repository_url": "https://github.com/example/demo",
    })
    gitee = client.post("/api/projects", json={
        "name": "Gitee demo",
        "source_type": "gitee",
        "repository_url": "https://gitee.com/example/demo-cn.git",
    })

    assert github.status_code == 200
    assert github.json()["source_type"] == "github"
    assert github.json()["source_uri"] == "https://github.com/example/demo.git"
    assert Path(github.json()["root_path"]).is_dir()
    assert gitee.status_code == 200
    assert gitee.json()["source_type"] == "gitee"
    assert gitee.json()["source_uri"] == "https://gitee.com/example/demo-cn.git"


def test_remote_project_scan_uses_cache_when_update_is_unavailable(tmp_path: Path) -> None:
    client = make_client(tmp_path, remote_warnings=["remote_update_unavailable"])
    project = client.post("/api/projects", json={
        "source_type": "gitee",
        "repository_url": "https://gitee.com/example/demo",
    }).json()

    scanned = client.post(f"/api/projects/{project['id']}/scan")

    assert scanned.status_code == 200
    assert scanned.json()["file_count"] == 1
    assert scanned.json()["route_count"] == 1
    assert "remote_update_unavailable" in scanned.json()["warnings"]


def test_project_scan_caps_semantic_index_wait_time(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    container = client.app.state.container
    object.__setattr__(container.settings, "project_index_timeout_seconds", 0.01)
    container.__dict__["project_indexer"] = SlowProjectIndexer()
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("def run(): return 1", encoding="utf-8")
    project = client.post("/api/projects", json={"name": "fast", "root_path": str(source)}).json()

    started = time.perf_counter()
    scanned = client.post(f"/api/projects/{project['id']}/scan")
    elapsed = time.perf_counter() - started

    assert scanned.status_code == 200
    assert elapsed < 0.2
    assert "project_semantic_index_timeout" in scanned.json()["warnings"]


def test_remote_project_chat_uses_local_overview_when_semantic_services_are_unavailable(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    container = client.app.state.container
    container.embeddings = UnavailableEmbeddings()
    container.chat_model = PromptEchoModel()
    for name in ("project_indexer", "project_retriever", "graph", "chat_use_case"):
        container.__dict__.pop(name, None)
    project = client.post("/api/projects", json={
        "name": "Gitee Q&A",
        "source_type": "gitee",
        "repository_url": "https://gitee.com/example/demo",
    }).json()

    scanned = client.post(f"/api/projects/{project['id']}/scan")
    session = client.post(
        "/api/chat/session", json={"project_id": project["id"]}
    ).json()
    response = client.post("/api/chat/stream", json={
        "message": "简单介绍一下这个项目的主要技术栈",
        "session_id": session["session_id"],
        "project_id": project["id"],
    })

    assert "project_semantic_index_unavailable" in scanned.json()["warnings"]
    assert response.status_code == 200
    assert "项目名称：Gitee Q&A" in response.text
    assert "已识别技术栈：python" in response.text
    assert "project_semantic_retrieval_unavailable" in response.text


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


def test_project_api_supports_renaming_without_changing_source(tmp_path: Path) -> None:
    source = tmp_path / "rename-source"
    source.mkdir()
    (source / "main.py").write_text("value = 1", encoding="utf-8")
    client = make_client(tmp_path)
    created = client.post(
        "/api/projects", json={"name": "旧项目名", "root_path": str(source)}
    ).json()

    response = client.patch(
        f"/api/projects/{created['id']}", json={"name": "外卖管理系统"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "外卖管理系统"
    assert response.json()["root_path"] == created["root_path"]
    assert client.get(f"/api/projects/{created['id']}").json()["name"] == "外卖管理系统"


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


def test_model_provider_api_supports_editing_without_exposing_secret(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    created = client.post("/api/model-providers", json={
        "name": "Old name",
        "provider_type": "openai_compatible",
        "base_url": "https://example.test/v1",
        "model_name": "example-chat",
        "api_key": "sk-super-secret",
    }).json()

    response = client.patch(f"/api/model-providers/{created['id']}", json={
        "name": "New name",
        "model_name": "example-chat-v2",
        "api_key": "",
    })

    assert response.status_code == 200
    assert response.json()["name"] == "New name"
    assert response.json()["model_name"] == "example-chat-v2"
    assert response.json()["has_api_key"] is True
    assert "api_key" not in response.json()


def test_model_comparison_api_returns_two_independent_answers(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    container = client.app.state.container
    first = client.post("/api/model-providers", json={
        "name": "模型 A",
        "provider_type": "openai_compatible",
        "base_url": "https://a.example.test/v1",
        "model_name": "model-a",
        "api_key": "sk-a",
    }).json()
    second = client.post("/api/model-providers", json={
        "name": "模型 B",
        "provider_type": "openai_compatible",
        "base_url": "https://b.example.test/v1",
        "model_name": "model-b",
        "api_key": "sk-b",
    }).json()
    container.model_gateway = ModelGateway({
        first["id"]: FixedModel("回答 A"),
        second["id"]: FixedModel("回答 B"),
    })
    container.__dict__.pop("chat_use_case", None)
    session_id = client.post("/api/chat/session").json()["session_id"]

    result = client.post("/api/models/compare", json={
        "message": "比较模型",
        "model_ids": [first["id"], second["id"]],
        "session_id": session_id,
    })

    assert result.status_code == 200
    assert [item["answer"] for item in result.json()["items"]] == ["回答 A", "回答 B"]
    assert [item["provider_name"] for item in result.json()["items"]] == ["模型 A", "模型 B"]
    assert [item["model_name"] for item in result.json()["items"]] == ["model-a", "model-b"]
    assert result.json()["session_id"] == session_id
    messages = client.get(f"/api/conversations/{session_id}/messages").json()["items"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[-1]["metadata"]["type"] == "model_comparison"
    assert messages[-1]["metadata"]["items"][0]["provider_name"] == "模型 A"


def test_delete_project_removes_project_vectors_before_local_data(tmp_path: Path) -> None:
    source = tmp_path / "delete-source"
    source.mkdir()
    (source / "main.py").write_text("value = 1", encoding="utf-8")
    client = make_client(tmp_path)
    project = client.post("/api/projects", json={"name": "delete", "root_path": str(source)}).json()
    client.post(f"/api/projects/{project['id']}/scan")
    vector_index = client.app.state.container.vector_index

    result = client.delete(f"/api/projects/{project['id']}")

    assert result.status_code == 200
    assert vector_index.deletes[0][0] == f"project_{project['id']}"
    assert vector_index.deletes[0][1]
