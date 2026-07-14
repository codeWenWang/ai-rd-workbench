# Local Project Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete local multi-project, read-only code analysis workflow with project chat, four generated artifacts, multi-model switching/comparison, and real token streaming.

**Architecture:** Extend the existing FastAPI modular monolith with isolated project source, scanning, parsing, analysis, retrieval, artifact, and model gateway modules. Keep SQLite authoritative, use one Pinecone namespace per project for semantic code retrieval, and keep the current knowledge and memory flows compatible.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, LangChain, LangGraph, Pinecone, SQLite FTS5, Python AST, vanilla JavaScript, Mermaid, Node test runner, pytest.

---

### Task 1: Establish a clean Git baseline

**Files:**
- Modify: `.gitignore`
- Track: `backend/`, `frontend/`, `scripts/`, `start.bat`, existing docs

- [ ] **Step 1: Add editor metadata exclusions**

```gitignore
.idea/
.cursor/
```

- [ ] **Step 2: Verify secrets and generated data remain ignored**

Run:

```powershell
git check-ignore -v backend/.env .venv backend/data/app.db .idea .cursor
```

Expected: every path is matched by `.gitignore`.

- [ ] **Step 3: Run the existing baseline tests**

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
node --test *.test.mjs js\api.test.mjs
```

Expected: current backend and frontend tests pass before feature work.

- [ ] **Step 4: Commit the baseline separately**

```powershell
git add .gitignore backend frontend scripts start.bat docs 研发文档.md
git commit -m "chore: 建立项目代码基线"
```

### Task 2: Add project domain and persistence

**Files:**
- Modify: `backend/app/domain/entities.py`
- Modify: `backend/app/domain/ports.py`
- Modify: `backend/app/infrastructure/db/models.py`
- Modify: `backend/app/infrastructure/db/session.py`
- Modify: `backend/app/infrastructure/db/repositories.py`
- Create: `backend/app/application/projects.py`
- Test: `backend/tests/unit/projects/test_project_repository.py`

- [ ] **Step 1: Write failing repository tests**

```python
def test_projects_are_created_and_listed(container, tmp_path):
    project = container.projects.create(name="demo", root_path=str(tmp_path), source_type="local")
    assert container.projects.get(project.id).root_path == str(tmp_path.resolve())
    assert [item.id for item in container.projects.list()] == [project.id]


def test_conversation_can_be_bound_to_project(container, tmp_path):
    project = container.projects.create(name="demo", root_path=str(tmp_path), source_type="local")
    conversation = container.conversations.create("项目问答", project_id=project.id)
    assert conversation.project_id == project.id
```

- [ ] **Step 2: Run the tests and confirm they fail**

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/unit/projects/test_project_repository.py -q
```

Expected: failure because project entities and repositories do not exist.

- [ ] **Step 3: Add focused project entities and ports**

```python
@dataclass(slots=True)
class Project:
    id: str
    name: str
    root_path: str
    source_type: str = "local"
    status: str = "pending"
    source_revision: str | None = None
    tech_stack: list[str] = field(default_factory=list)
    last_scanned_at: datetime | None = None


class ProjectRepository(Protocol):
    def create(self, *, name: str, root_path: str, source_type: str = "local") -> Project: ...
    def get(self, project_id: str) -> Project | None: ...
    def list(self) -> list[Project]: ...
    def delete(self, project_id: str) -> None: ...
```

- [ ] **Step 4: Add SQLAlchemy tables and SQLite repositories**

Add `ProjectModel`, `ProjectFileModel`, `ProjectSymbolModel`, `ProjectRelationModel`, `ProjectChunkModel`, `ProjectAnalysisJobModel`, `AnalysisArtifactModel`, `ModelProviderModel`, and `ModelProfileModel`. Extend `ConversationModel` with nullable `project_id`. Create `project_chunks_fts` in `Database.create_schema()`.

- [ ] **Step 5: Add `ProjectUseCase` validation**

```python
class ProjectUseCase:
    def create(self, name: str, root_path: str):
        root = Path(root_path).expanduser().resolve()
        if not root.is_dir():
            raise ValidationError("项目目录不存在或不可读取")
        return self.projects.create(name=name.strip() or root.name, root_path=str(root))
```

- [ ] **Step 6: Run project and regression tests**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/projects tests/integration/test_backend_flow.py -q
```

- [ ] **Step 7: Commit**

```powershell
git add backend/app backend/tests/unit/projects
git commit -m "feat: 添加本地项目领域模型"
```

### Task 3: Implement safe incremental project scanning

**Files:**
- Create: `backend/app/infrastructure/projects/source.py`
- Create: `backend/app/infrastructure/projects/scanner.py`
- Create: `backend/app/infrastructure/projects/parsers.py`
- Create: `backend/app/application/project_analysis.py`
- Test: `backend/tests/unit/projects/test_scanner.py`
- Test: `backend/tests/unit/projects/test_parsers.py`

- [ ] **Step 1: Write failing safety and parser tests**

```python
def test_scanner_ignores_secrets_and_dependencies(tmp_path):
    (tmp_path / "app.py").write_text("def run(): return 1", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    result = LocalProjectScanner().scan(tmp_path)
    assert [item.relative_path for item in result.files] == ["app.py"]


def test_python_parser_extracts_fastapi_route():
    facts = PythonAstParser().parse("api.py", "@router.get('/items')\ndef list_items():\n    return []")
    assert facts.routes[0].method == "GET"
    assert facts.routes[0].path == "/items"
```

- [ ] **Step 2: Confirm tests fail**

Run:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/projects/test_scanner.py tests/unit/projects/test_parsers.py -q
```

- [ ] **Step 3: Implement `LocalDirectorySource` and scanner rules**

Use a fixed extension allowlist and ignored directory/file sets. Resolve every discovered file and require `resolved_file.is_relative_to(root)` before reading it. Limit individual source files to 1 MiB for the first version.

- [ ] **Step 4: Implement structured parsers**

Use Python `ast` for imports, classes, functions, calls, and FastAPI decorators. Use a small deterministic parser for JavaScript ES module imports/exports and HTML script/style references. Return `ParsedFile` facts rather than generated prose.

- [ ] **Step 5: Implement hash-based rescan orchestration**

`ProjectAnalysisUseCase.scan(project_id)` compares relative path and SHA-256, reparses changed files, removes deleted file facts, rebuilds affected chunks, and calculates one project revision hash.

- [ ] **Step 6: Run tests and commit**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/projects -q
git add backend/app backend/tests/unit/projects
git commit -m "feat: 添加安全项目扫描与静态解析"
```

### Task 4: Add project retrieval and four artifacts

**Files:**
- Create: `backend/app/infrastructure/retrieval/project.py`
- Create: `backend/app/application/artifacts.py`
- Create: `backend/app/infrastructure/artifacts/mermaid.py`
- Create: `backend/app/infrastructure/artifacts/api_docs.py`
- Modify: `backend/app/infrastructure/vectorstores/pinecone.py`
- Test: `backend/tests/unit/projects/test_artifacts.py`
- Test: `backend/tests/integration/test_project_flow.py`

- [ ] **Step 1: Write failing artifact tests**

```python
def test_architecture_artifact_contains_mermaid_and_source_revision(project_fixture):
    artifact = project_fixture.artifacts.generate(project_fixture.project.id, "architecture")
    assert artifact.format == "mermaid"
    assert artifact.content.startswith("flowchart")
    assert artifact.source_revision == project_fixture.project.source_revision


def test_api_document_lists_static_fastapi_route(project_fixture):
    artifact = project_fixture.artifacts.generate(project_fixture.project.id, "api_docs")
    assert "GET /api/health/live" in artifact.content
```

- [ ] **Step 2: Confirm tests fail**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/projects/test_artifacts.py tests/integration/test_project_flow.py -q
```

- [ ] **Step 3: Implement project FTS and Pinecone indexing**

Store code chunks in `project_chunks` and `project_chunks_fts`. Use namespace `project_<project_id>` for vector upsert/query/delete. Include relative path, start line, end line, symbol, and project ID in metadata.

- [ ] **Step 4: Generate deterministic artifact drafts**

Generate architecture, flow, sequence, and API documentation from stored facts. Mermaid generators must escape labels and output only supported Mermaid syntax. Mark inferred edges with an `inferred` label.

- [ ] **Step 5: Mark artifacts stale after rescanning**

When project revision changes, update older artifact rows from `ready` to `stale`.

- [ ] **Step 6: Run tests and commit**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/projects tests/integration/test_project_flow.py -q
git add backend/app backend/tests
git commit -m "feat: 添加项目检索与分析制品"
```

### Task 5: Add model providers and fair comparison

**Files:**
- Create: `backend/app/infrastructure/llm/gateway.py`
- Create: `backend/app/infrastructure/security/secrets.py`
- Create: `backend/app/application/models.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/dependencies.py`
- Test: `backend/tests/unit/infrastructure/test_model_gateway.py`

- [ ] **Step 1: Write failing gateway tests**

```python
async def test_compare_uses_identical_messages_for_both_models():
    first, second = RecordingModel("A"), RecordingModel("B")
    result = await ModelGateway({"a": first, "b": second}).compare([message], ["a", "b"])
    assert first.messages == second.messages == [message]
    assert [item.model_id for item in result] == ["a", "b"]


def test_provider_serialization_never_returns_api_key(client):
    item = client.post("/api/model-providers", json=provider_payload).json()
    assert "api_key" not in item
```

- [ ] **Step 2: Confirm tests fail**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/infrastructure/test_model_gateway.py -q
```

- [ ] **Step 3: Implement provider adapters**

Use `ChatOpenAI` for both DashScope and generic OpenAI-compatible profiles. Build clients lazily from provider metadata and secret references. Keep the existing DashScope Embedding adapter unchanged.

- [ ] **Step 4: Implement local secret storage**

Store provider secrets in `backend/data/model-secrets.json`, excluded by the existing `backend/data/` rule. Return only `has_api_key: true/false` through APIs and redact credentials from errors.

- [ ] **Step 5: Implement comparison orchestration**

Run at most two model calls with `asyncio.gather(..., return_exceptions=True)`, using one shared retrieved context. A failure in one model must not discard the other result.

- [ ] **Step 6: Run tests and commit**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/unit/infrastructure/test_model_gateway.py -q
git add backend/app backend/tests/unit/infrastructure
git commit -m "feat: 添加多模型配置与对比"
```

### Task 6: Replace fake streaming with real model streaming

**Files:**
- Modify: `backend/app/application/chat.py`
- Modify: `backend/app/workflows/chat_graph.py`
- Modify: `backend/app/workflows/nodes.py`
- Modify: `backend/app/workflows/state.py`
- Modify: `backend/app/api/chat_v2.py`
- Modify: `backend/app/domain/entities.py`
- Test: `backend/tests/integration/test_streaming_chat.py`

- [ ] **Step 1: Write a timing-sensitive failing streaming test**

```python
class DelayedStreamingModel:
    async def astream(self, messages):
        yield "第一段"
        await asyncio.sleep(0.05)
        yield "第二段"


def test_stream_emits_model_chunks_without_fixed_24_character_slicing(client):
    body = client.post("/api/chat/stream", json={"message": "测试"}).text
    assert '"token": "第一段"' in body
    assert '"token": "第二段"' in body
```

- [ ] **Step 2: Confirm the current endpoint fails the contract**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/integration/test_streaming_chat.py -q
```

- [ ] **Step 3: Add `ChatUseCase.stream_chat()`**

Persist user and pending assistant messages first, run retrieval and query rewriting, then iterate `model.astream()`. Yield `session`, `stage`, `token`, `citations`, `warning`, and `done` events while accumulating the final assistant text.

- [ ] **Step 4: Handle disconnect and cancellation**

Add `MessageStatus.CANCELLED`. On cancellation save partial text and update the message status. On model failure mark it `failed` with a redacted error.

- [ ] **Step 5: Remove fixed answer slicing from the API**

`/api/chat/stream` must forward use-case events directly and must not call the blocking `chat()` method first.

- [ ] **Step 6: Run streaming and regression tests, then commit**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/integration/test_streaming_chat.py tests/integration/test_backend_flow.py -q
git add backend/app backend/tests/integration
git commit -m "feat: 实现真实模型流式输出"
```

### Task 7: Expose project, artifact, and model APIs

**Files:**
- Create: `backend/app/api/projects.py`
- Create: `backend/app/api/artifacts.py`
- Create: `backend/app/api/model_providers.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/dependencies.py`
- Test: `backend/tests/integration/test_project_api.py`

- [ ] **Step 1: Write failing endpoint contract tests**

Cover project create/list/detail/delete, scan, file list, artifact generate/list/detail, provider create/list/test, and project-bound chat. Assert `/docs` returns 404 while `/openapi.json` remains available.

- [ ] **Step 2: Confirm tests fail**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/integration/test_project_api.py -q
```

- [ ] **Step 3: Implement thin FastAPI routers**

Routers validate request bodies and delegate to use cases. Project creation accepts `name` and `root_path`; scan and artifact generation return persisted job/result status; no endpoint returns an absolute source path in citations.

- [ ] **Step 4: Wire the dependency container**

Register project repositories, scanner, parser registry, project retriever, artifact use case, secret store, provider use case, and model gateway as cached properties.

- [ ] **Step 5: Remove the custom platform `/docs` route**

Delete the `FileResponse(frontend_dir / "docs.html")` route and stop linking `frontend/docs.html`. Keep FastAPI `docs_url=None` and `/openapi.json`.

- [ ] **Step 6: Run API tests and commit**

```powershell
..\.venv\Scripts\python.exe -m pytest tests/integration/test_project_api.py -q
git add backend/app backend/tests/integration
git commit -m "feat: 暴露项目分析与模型接口"
```

### Task 8: Build the project workspace frontend and verify the full flow

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/css/style.css`
- Modify: `frontend/js/api.js`
- Modify: `frontend/js/app.js`
- Modify: `frontend/js/chat.js`
- Create: `frontend/js/projects.js`
- Create: `frontend/js/artifacts.js`
- Create: `frontend/js/models.js`
- Delete: `frontend/docs.html`
- Modify: `frontend/workbench.test.mjs`
- Modify: `frontend/js/api.test.mjs`
- Modify: `frontend/asset-version.test.mjs`

- [ ] **Step 1: Update failing frontend structure tests**

Assert the sidebar contains a project selector, expandable project analysis group, architecture/flow/sequence/API-document views, model settings, and bottom diagnostics control. Assert it does not contain `href="/docs"`.

- [ ] **Step 2: Run tests and confirm they fail**

```powershell
cd frontend
node --test *.test.mjs js\api.test.mjs
```

- [ ] **Step 3: Implement project and analysis UI**

Add project selector and add-project dialog, project overview, scan progress, artifact tabs, Mermaid rendering, stale state, and regenerate actions. Keep the sidebar collapsible and recent conversations independently scrollable.

- [ ] **Step 4: Implement model settings and comparison UI**

Add provider configuration dialog, chat model selector, comparison toggle, and two response columns only while comparison is active. Never render stored API keys.

- [ ] **Step 5: Render true incremental streaming**

Update one assistant message as `token` events arrive. Display stage text without resizing the composer. On `done`, attach citations and refresh conversation history.

- [ ] **Step 6: Move diagnostics and remove platform docs**

Replace the primary diagnostics navigation item with a footer status button that opens the existing diagnostics content in a drawer. Delete `frontend/docs.html` and its docs-only CSS.

- [ ] **Step 7: Run all automated tests**

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
node --test *.test.mjs js\api.test.mjs
```

Expected: all backend and frontend tests pass.

- [ ] **Step 8: Run browser verification**

Start `start.bat`, then verify desktop and mobile flows: add the current repository, scan it, generate four artifacts, ask a project question with source citations, switch models, compare two models, observe incremental tokens, reopen a recent project conversation, and open diagnostics from the footer.

- [ ] **Step 9: Commit final frontend and verification changes**

```powershell
git add frontend backend/tests docs start.bat
git commit -m "feat: 完成本地项目智能分析工作台"
```

