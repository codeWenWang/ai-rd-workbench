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
