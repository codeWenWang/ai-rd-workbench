from pathlib import Path

import pytest

from app.application.artifacts import ArtifactUseCase
from app.application.project_analysis import ProjectAnalysisUseCase
from app.infrastructure.db.repositories import (
    SqliteProjectAnalysisRepository,
    SqliteProjectRepository,
)
from app.infrastructure.db.session import Database
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
        ("api_docs", "markdown", "GET /items"),
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
    assert "Spring MVC" in api_docs
    assert "server/src/main/java/demo/RepositoryController.java" in api_docs
    assert "FastAPI" not in architecture + flow + sequence + api_docs


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
