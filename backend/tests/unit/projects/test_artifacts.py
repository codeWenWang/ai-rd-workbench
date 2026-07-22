from pathlib import Path

import pytest

from app.application.artifacts import ArtifactUseCase
from app.application.project_analysis import ProjectAnalysisUseCase
from app.infrastructure.db.repositories import (
    SqliteProjectAnalysisRepository,
    SqliteProjectRepository,
)
from app.infrastructure.db.session import Database
from app.infrastructure.artifacts.mermaid import render_architecture, render_sequence
from app.infrastructure.artifacts.api_docs import _fallback_title
from app.infrastructure.projects.insights import (
    ProjectEndpointInsight,
    ProjectInsight,
    ProjectModuleInsight,
)
from app.infrastructure.projects.parsers import ParserRegistry
from app.infrastructure.projects.scanner import LocalProjectScanner


@pytest.fixture
def analyzed_project(tmp_path: Path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "api.py").write_text(
        "from fastapi import APIRouter\n"
        "from app.service import load_items\n"
        "router = APIRouter()\n"
        "@router.get('/items')\n"
        "def list_items(): return load_items()\n",
        encoding="utf-8",
    )
    database = Database(f"sqlite:///{(tmp_path / 'artifacts.db').as_posix()}")
    database.create_schema()
    projects = SqliteProjectRepository(database.session_factory)
    analysis = SqliteProjectAnalysisRepository(database.session_factory)
    project = projects.create(name="demo", root_path=str(root))
    ProjectAnalysisUseCase(
        projects, analysis, LocalProjectScanner(), ParserRegistry()
    ).scan(project.id)
    return root, projects, analysis, project


@pytest.mark.parametrize(
    ("artifact_type", "expected_format", "expected_text"),
    [
        ("architecture", "mermaid", "flowchart"),
        ("flow", "mermaid", "GET /items"),
        ("sequence", "mermaid", "sequenceDiagram"),
        ("api_docs", "markdown", "**请求路径：** `/items`"),
    ],
)
def test_generates_four_project_artifacts(
    analyzed_project, artifact_type: str, expected_format: str, expected_text: str
) -> None:
    _, projects, analysis, project = analyzed_project
    artifact = ArtifactUseCase(projects, analysis).generate(project.id, artifact_type)

    assert artifact.format == expected_format
    assert expected_text in artifact.content
    assert artifact.source_revision == projects.get(project.id).source_revision
    assert artifact.status == "ready"


def test_rescan_marks_existing_artifact_stale(analyzed_project) -> None:
    root, projects, analysis, project = analyzed_project
    artifacts = ArtifactUseCase(projects, analysis)
    artifact = artifacts.generate(project.id, "architecture")

    (root / "new.py").write_text("def added(): return 1", encoding="utf-8")
    ProjectAnalysisUseCase(
        projects, analysis, LocalProjectScanner(), ParserRegistry()
    ).scan(project.id)

    assert analysis.get_artifact(artifact.id).status == "stale"


def test_project_full_text_search_returns_source_location(analyzed_project) -> None:
    _, _, analysis, project = analyzed_project

    results = analysis.search_chunks(project.id, "load_items", limit=5)

    assert results
    assert results[0].relative_path == "api.py"
    assert results[0].start_line == 1


def test_project_search_accepts_user_question_punctuation(analyzed_project) -> None:
    _, _, analysis, project = analyzed_project

    results = analysis.search_chunks(project.id, "load_items 是什么？", limit=5)

    assert results and results[0].relative_path == "api.py"


def test_java_maven_artifacts_are_module_oriented_and_framework_neutral(tmp_path: Path) -> None:
    root = tmp_path / "java-source"
    for module in ("core", "storage-file", "server"):
        (root / module / "src" / "main" / "java" / "demo").mkdir(parents=True)
    (root / "pom.xml").write_text("""
        <project><artifactId>demo</artifactId><modules>
          <module>core</module><module>storage-file</module><module>server</module>
        </modules></project>
    """, encoding="utf-8")
    (root / "core" / "pom.xml").write_text(
        "<project><artifactId>demo-core</artifactId></project>", encoding="utf-8",
    )
    (root / "storage-file" / "pom.xml").write_text("""
        <project><artifactId>demo-storage-file</artifactId><dependencies>
          <dependency><artifactId>demo-core</artifactId></dependency>
        </dependencies></project>
    """, encoding="utf-8")
    (root / "server" / "pom.xml").write_text("""
        <project><artifactId>demo-server</artifactId><dependencies>
          <dependency><artifactId>demo-core</artifactId></dependency>
          <dependency><artifactId>demo-storage-file</artifactId></dependency>
        </dependencies></project>
    """, encoding="utf-8")
    (root / "core" / "src" / "main" / "java" / "demo" / "RepositoryService.java").write_text(
        "package demo; public class RepositoryService {}", encoding="utf-8",
    )
    (root / "server" / "src" / "main" / "java" / "demo" / "DemoApplication.java").write_text(
        "@SpringBootApplication public class DemoApplication { public static void main(String[] args) {} }",
        encoding="utf-8",
    )
    (root / "server" / "src" / "main" / "java" / "demo" / "RepositoryController.java").write_text("""
        @RestController
        @RequestMapping("/repository")
        public class RepositoryController {
            @GetMapping("/items")
            public String items() { return "ok"; }

            @DeleteMapping("/items")
            public void deleteItem() {}
        }
    """, encoding="utf-8")
    database = Database(f"sqlite:///{(tmp_path / 'java-artifacts.db').as_posix()}")
    database.create_schema()
    projects = SqliteProjectRepository(database.session_factory)
    analysis = SqliteProjectAnalysisRepository(database.session_factory)
    project = projects.create(name="java-demo", root_path=str(root))
    ProjectAnalysisUseCase(
        projects, analysis, LocalProjectScanner(), ParserRegistry()
    ).scan(project.id)
    artifacts = ArtifactUseCase(projects, analysis)

    architecture = artifacts.generate(project.id, "architecture").content
    flow = artifacts.generate(project.id, "flow").content
    sequence = artifacts.generate(project.id, "sequence").content
    api_docs = artifacts.generate(project.id, "api_docs").content

    assert all(module in architecture for module in ("core", "server", "storage-file"))
    assert "server --> core" in architecture
    assert "server --> storage_file" in architecture
    assert "GET /repository/items" in flow
    assert "RepositoryController.items" in flow
    assert "Spring MVC" in flow
    assert "handler --> step_0_core" in flow
    assert "handler --> step_1_storage_file" in flow
    assert "step_0_core --> step_1_storage_file" not in flow
    assert "RepositoryController.items" in sequence
    assert "GET /repository/items" in sequence
    assert "**请求路径：** `/repository/items`" in api_docs
    assert "**请求方式：** `GET`" in api_docs
    assert "server/src/main/java/demo/RepositoryController.java" in api_docs
    assert "FastAPI" not in architecture + flow + sequence + api_docs


def test_spring_api_docs_are_normalized_and_infer_request_response_examples(tmp_path: Path) -> None:
    root = tmp_path / "department-api"
    source = root / "src" / "main" / "java" / "demo"
    source.mkdir(parents=True)
    (root / "pom.xml").write_text(
        "<project><artifactId>department-api</artifactId></project>", encoding="utf-8"
    )
    (source / "DepartmentController.java").write_text("""
        @RestController
        @RequestMapping("/depts")
        public class DepartmentController {
            /** 部门列表查询 */
            @GetMapping
            public Result<List<Dept>> list() { return null; }

            /** 删除部门 */
            @DeleteMapping("/{id}")
            public Result<Void> delete(@PathVariable Long id) { return null; }

            /** 添加部门 */
            @PostMapping
            public Result<Void> add(@RequestBody DeptCreateRequest request) { return null; }

            /** 根据ID查询 */
            @GetMapping("/{id}")
            public Result<Dept> get(@PathVariable("id") Long departmentId) { return null; }

            /** 修改部门 */
            @PutMapping
            public Result<Void> update(@RequestBody DeptUpdateRequest request) { return null; }

            @PatchMapping("/{id}")
            public Result<Void> patch(@PathVariable Long id) { return null; }

            public record Dept(
                Long id,
                String name,
                LocalDateTime createTime,
                LocalDateTime updateTime
            ) {}

            public record DeptCreateRequest(String name) {}
            public record DeptUpdateRequest(Long id, String name) {}
        }
    """, encoding="utf-8")
    (source / "AdminUiController.java").write_text("""
        @Controller
        public class AdminUiController {
            @GetMapping("/")
            public String index() { return "index"; }
        }
    """, encoding="utf-8")
    (source / "Result.java").write_text("""
        public class Result<T> {
            private static final long serialVersionUID = 1L;
            private int code;
            private String msg;
            private T data;
        }
    """, encoding="utf-8")
    database = Database(f"sqlite:///{(tmp_path / 'department.db').as_posix()}")
    database.create_schema()
    projects = SqliteProjectRepository(database.session_factory)
    analysis = SqliteProjectAnalysisRepository(database.session_factory)
    project = projects.create(name="部门管理", root_path=str(root))
    ProjectAnalysisUseCase(
        projects, analysis, LocalProjectScanner(), ParserRegistry()
    ).scan(project.id)

    content = ArtifactUseCase(projects, analysis).generate(project.id, "api_docs").content

    assert "### 1.1 部门列表查询" in content
    assert "**请求路径：** `/depts`" in content
    assert "**请求方式：** `GET`" in content
    assert "**请求参数：** 无" in content
    assert '"code": 0' in content
    assert '"msg": "string"' in content
    assert '"data": [' in content
    assert '"createTime": "string"' in content
    assert "### 1.2 删除部门" in content
    assert "### 1.3 添加部门" in content
    assert '"name": "string"' in content
    assert "### 1.4 根据ID查询" in content
    assert "### 1.5 修改部门" in content
    assert '"id": 0' in content
    assert "serialVersionUID" not in content
    assert "请求样例：** `/depts/1`" in content
    assert "`PATCH`" not in content
    assert "AdminUiController" not in content


def test_api_docs_use_type_templates_without_static_notes_and_link_endpoint_source(tmp_path: Path) -> None:
    root = tmp_path / "realistic-api"
    source = root / "src" / "main" / "java" / "demo"
    source.mkdir(parents=True)
    (root / "pom.xml").write_text(
        "<project><artifactId>realistic-api</artifactId></project>",
        encoding="utf-8",
    )
    (source / "PersonController.java").write_text("""
        @RestController
        @RequestMapping("/people")
        public class PersonController {
            @PostMapping
            public Person create(@RequestBody Person request) { return null; }
            public record Person(String name, String objectKey, String region, String state) {}
        }
    """, encoding="utf-8")
    database = Database(f"sqlite:///{(tmp_path / 'realistic.db').as_posix()}")
    database.create_schema()
    projects = SqliteProjectRepository(database.session_factory)
    analysis = SqliteProjectAnalysisRepository(database.session_factory)
    project = projects.create(name="realistic", root_path=str(root))
    ProjectAnalysisUseCase(
        projects, analysis, LocalProjectScanner(), ParserRegistry()
    ).scan(project.id)

    content = ArtifactUseCase(projects, analysis).generate(project.id, "api_docs").content

    assert '"name": "string"' in content
    assert '"objectKey": "string"' in content
    assert '"region": "string"' in content
    assert '"state": "string"' in content
    assert "张三" not in content
    assert "demo-bucket/tasks/1" not in content
    assert "cn-hangzhou" not in content
    assert "READY" not in content
    assert "示例值" not in content
    assert "结构根据源码静态推断" not in content
    assert "source://src/main/java/demo/PersonController.java" in content


def test_sequence_uses_ordered_participants_activation_and_error_branch() -> None:
    insight = ProjectInsight(
        project_type="Java / Spring",
        modules=[
            ProjectModuleInsight("web", "入口服务", 3, dependencies=["core", "message-queue", "storage"]),
            ProjectModuleInsight("core", "核心", 4),
            ProjectModuleInsight("message-queue", "功能模块", 2),
            ProjectModuleInsight("storage", "持久化", 3),
        ],
        endpoints=[
            ProjectEndpointInsight(
                "GET", "/users/{id}", "UserController.get", "web/UserController.java", 18,
                "Spring MVC", "web",
            )
        ],
    )

    content = render_sequence(insight)

    assert content.index("actor U as 外部用户") < content.index("participant G as 前端 / 网关【web】")
    assert content.index("participant G as 前端 / 网关【web】") < content.index("participant B as 业务服务【UserController】")
    assert content.index("业务服务【core】") < content.index("中间件【message-queue】")
    assert content.index("中间件【message-queue】") < content.index("数据库【storage】")
    assert "activate G" in content and "deactivate G" in content
    assert "activate B" in content and "deactivate B" in content
    assert "alt 正常流程" in content
    assert "else 关键异常" in content
    assert "U->>G: GET /users/{id}(id) : 发起请求" in content
    assert "G-->>U:" in content
    assert "Note over" not in content


def test_sample_project_is_a_classroom_ready_multimodule_crud_demo(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "fixtures" / "sample_project"
    database = Database(f"sqlite:///{(tmp_path / 'sample-demo.db').as_posix()}")
    database.create_schema()
    projects = SqliteProjectRepository(database.session_factory)
    analysis = SqliteProjectAnalysisRepository(database.session_factory)
    project = projects.create(name="研发任务管理演示", root_path=str(root))

    summary = ProjectAnalysisUseCase(
        projects, analysis, LocalProjectScanner(), ParserRegistry()
    ).scan(project.id)
    artifacts = ArtifactUseCase(projects, analysis)
    architecture = artifacts.generate(project.id, "architecture").content
    flow = artifacts.generate(project.id, "flow").content
    sequence = artifacts.generate(project.id, "sequence").content
    api_docs = artifacts.generate(project.id, "api_docs").content

    assert summary.file_count >= 16
    assert summary.route_count == 6
    assert all(
        module in architecture
        for module in ("api", "core-service", "data-repository", "domain")
    )
    assert "api --> core_service" in architecture
    assert "api --> data_repository" in architecture
    assert "core_service --> data_repository" in architecture
    assert "GET /api/tasks" in flow
    assert "TaskController.listTasks" in flow
    assert "GET /api/tasks" in sequence
    assert "TaskController.listTasks" in sequence
    assert "查询研发任务列表" in api_docs
    assert "创建研发任务" in api_docs
    assert "根据 ID 查询研发任务" in api_docs
    assert "更新研发任务" in api_docs
    assert "删除研发任务" in api_docs
    assert "完成研发任务" in api_docs
    assert '"code": 0' in api_docs
    assert '"message": "string"' in api_docs
    assert "请求样例：** `/api/tasks/1`" in api_docs


def test_large_architecture_groups_modules_by_role() -> None:
    protocols = [
        ProjectModuleInsight(f"protocol-{index}", "协议适配", 3)
        for index in range(10)
    ]
    modules = [
        ProjectModuleInsight(
            "server", "入口服务", 20,
            dependencies=["core", "storage-file", *[item.name for item in protocols]],
        ),
        ProjectModuleInsight("core", "核心", 30),
        ProjectModuleInsight("storage-file", "存储", 8),
        *protocols,
    ]

    diagram = render_architecture(ProjectInsight("Java / Maven / Spring", modules=modules))

    assert 'layer_business["业务服务层 · 12 个模块' in diagram
    assert 'layer_data["数据层 · 1 个模块' in diagram
    assert "protocol-0（协议适配）" in diagram
    assert "layer_business --> layer_data" in diagram
    assert diagram.count("protocol-") < 10


def test_architecture_evidence_comments_include_layer_and_module() -> None:
    modules = [
        ProjectModuleInsight(
            "admin-ui", "界面", 2,
            evidence_paths=[
                "admin-ui/src/main/index.html",
                "admin-ui/src/main/app.js",
            ],
        ),
        ProjectModuleInsight(
            "core-service", "核心", 1,
            evidence_paths=["core-service/src/main/TaskService.java"],
        ),
        ProjectModuleInsight(
            "data-repository", "持久化", 1,
            evidence_paths=["data-repository/src/main/TaskRepository.java"],
        ),
    ]

    diagram = render_architecture(ProjectInsight("Java", modules=modules))

    assert "%% evidence: 客户端层 / admin-ui（界面） / admin-ui/src/main/index.html" in diagram
    assert "%% evidence: 业务服务层 / core-service（核心） / core-service/src/main/TaskService.java" in diagram
    assert "%% evidence: 数据层 / data-repository（持久化） / data-repository/src/main/TaskRepository.java" in diagram


def test_api_doc_fallback_titles_use_resource_and_crud_semantics() -> None:
    assert _fallback_title("BlobStoresController.list", "GET", "/internal/blob-stores") == "blob stores 列表查询"
    assert _fallback_title("BlobStoresController.create", "POST", "/internal/blob-stores") == "新增 blob stores"
    assert _fallback_title("BlobStoresController.update", "PUT", "/internal/blob-stores/{id}") == "修改 blob stores"
    assert _fallback_title("BlobStoresController.delete", "DELETE", "/internal/blob-stores/{id}") == "删除 blob stores"
    assert _fallback_title("BlobStoresController.check", "POST", "/internal/blob-stores/{id}/check") == "check 操作"
    assert _fallback_title("StatusController.status", "GET", "/internal/status") == "status 查询"
    assert _fallback_title("RepositoryController.put", "PUT", "/repository/{name}/**") == "修改 repository"


def test_large_source_file_is_split_into_embedding_sized_chunks(tmp_path: Path) -> None:
    root = tmp_path / "large-source"
    root.mkdir()
    (root / "large.py").write_text(
        "\n".join(f"value_{index} = {index}" for index in range(1200)),
        encoding="utf-8",
    )
    database = Database(f"sqlite:///{(tmp_path / 'large.db').as_posix()}")
    database.create_schema()
    projects = SqliteProjectRepository(database.session_factory)
    analysis = SqliteProjectAnalysisRepository(database.session_factory)
    project = projects.create(name="large", root_path=str(root))

    ProjectAnalysisUseCase(
        projects, analysis, LocalProjectScanner(), ParserRegistry()
    ).scan(project.id)
    chunks = analysis.list_chunks(project.id)

    assert len(chunks) > 1
    assert max(len(item.content) for item in chunks) <= 5000
