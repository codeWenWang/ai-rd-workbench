from pathlib import Path

from app.application.project_analysis import ProjectAnalysisUseCase
from app.infrastructure.db.repositories import (
    SqliteProjectAnalysisRepository,
    SqliteProjectRepository,
)
from app.infrastructure.db.session import Database
from app.infrastructure.projects.parsers import ParserRegistry
from app.infrastructure.projects.scanner import LocalProjectScanner


def make_use_case(tmp_path: Path):
    database = Database(f"sqlite:///{(tmp_path / 'analysis.db').as_posix()}")
    database.create_schema()
    projects = SqliteProjectRepository(database.session_factory)
    analysis = SqliteProjectAnalysisRepository(database.session_factory)
    return projects, analysis, ProjectAnalysisUseCase(
        projects,
        analysis,
        LocalProjectScanner(),
        ParserRegistry(),
    )


def test_scan_persists_files_symbols_routes_and_revision(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health(): return {'ok': True}\n",
        encoding="utf-8",
    )
    projects, analysis, use_case = make_use_case(tmp_path)
    project = projects.create(name="demo", root_path=str(root))

    summary = use_case.scan(project.id)

    assert summary.file_count == 1
    assert summary.symbol_count == 1
    assert summary.route_count == 1
    assert projects.get(project.id).source_revision == summary.revision
    assert analysis.list_files(project.id)[0].relative_path == "main.py"
    assert analysis.list_routes(project.id)[0].path == "/health"


def test_rescan_replaces_deleted_file_facts(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    source = root / "old.py"
    source.write_text("def old(): return 1", encoding="utf-8")
    projects, analysis, use_case = make_use_case(tmp_path)
    project = projects.create(name="demo", root_path=str(root))
    use_case.scan(project.id)

    source.unlink()
    (root / "new.py").write_text("def new(): return 2", encoding="utf-8")
    use_case.scan(project.id)

    assert [item.relative_path for item in analysis.list_files(project.id)] == ["new.py"]
    assert [item.name for item in analysis.list_symbols(project.id)] == ["new"]
