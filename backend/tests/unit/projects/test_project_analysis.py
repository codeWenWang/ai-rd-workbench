from pathlib import Path

from sqlalchemy.orm import Session

from app.application.project_analysis import ProjectAnalysisUseCase
from app.infrastructure.db.repositories import (
    SqliteProjectAnalysisRepository,
    SqliteProjectRepository,
)
from app.infrastructure.db.session import Database
from app.infrastructure.projects.parsers import ParsedFile, ParserRegistry
from app.infrastructure.projects.scanner import LocalProjectScanner, ScannedFile


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


def test_frontend_requests_are_available_to_interface_documentation(tmp_path: Path) -> None:
    root = tmp_path / "frontend"
    root.mkdir()
    (root / "client.ts").write_text(
        "export async function load() { return fetch('/api/items'); }\n"
        "export async function create(body) { return fetch('/api/items', { method: 'POST', body }); }\n"
        "export async function update(body) { return axios.put('/api/items/1', body); }\n"
        "export async function remove() { return axios.delete('/api/items/1'); }\n",
        encoding="utf-8",
    )
    projects, analysis, use_case = make_use_case(tmp_path)
    project = projects.create(name="frontend", root_path=str(root))

    summary = use_case.scan(project.id)
    routes = analysis.list_routes(project.id)

    assert summary.route_count == 4
    assert {(item.method, item.path) for item in routes} == {
        ("GET", "/api/items"), ("POST", "/api/items"),
        ("PUT", "/api/items/1"), ("DELETE", "/api/items/1"),
    }


def test_replace_scan_batches_database_flushes(tmp_path: Path, monkeypatch) -> None:
    projects, analysis, _ = make_use_case(tmp_path)
    project = projects.create(name="large", root_path=str(tmp_path))
    items = []
    for index in range(30):
        path = f"src/File{index}.java"
        scanned = ScannedFile(path, "java", 10, index, f"hash-{index}", "class Demo {}")
        items.append((scanned, ParsedFile(path, "java")))

    original_flush = Session.flush
    flush_calls = 0

    def counting_flush(session, *args, **kwargs):
        nonlocal flush_calls
        flush_calls += 1
        return original_flush(session, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", counting_flush)
    analysis.replace_scan(project.id, items)

    assert flush_calls <= 2
