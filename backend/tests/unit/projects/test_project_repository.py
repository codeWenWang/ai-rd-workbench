from pathlib import Path
import sqlite3

import pytest

from app.application.projects import ProjectUseCase
from app.domain.errors import ValidationError
from app.infrastructure.db.repositories import (
    SqliteConversationRepository,
    SqliteProjectRepository,
)
from app.infrastructure.db.session import Database
from app.infrastructure.projects.remote_git import RemoteRepository


def make_repositories(tmp_path: Path):
    database = Database(f"sqlite:///{(tmp_path / 'projects.db').as_posix()}")
    database.create_schema()
    return (
        SqliteProjectRepository(database.session_factory),
        SqliteConversationRepository(database.session_factory),
    )


def test_projects_are_created_and_listed(tmp_path: Path) -> None:
    projects, _ = make_repositories(tmp_path)

    project = projects.create(name="demo", root_path=str(tmp_path), source_type="local")

    assert project.root_path == str(tmp_path.resolve())
    assert [item.id for item in projects.list()] == [project.id]


def test_remote_project_preserves_source_uri_and_managed_path(tmp_path: Path) -> None:
    projects, _ = make_repositories(tmp_path)
    cache = tmp_path / "cache" / "github-demo"
    cache.mkdir(parents=True)

    project = projects.create(
        name="demo",
        root_path=str(cache),
        source_type="github",
        source_uri="https://github.com/example/demo.git",
    )

    loaded = projects.get(project.id)
    assert loaded is not None
    assert loaded.source_type == "github"
    assert loaded.root_path == str(cache.resolve())
    assert loaded.source_uri == "https://github.com/example/demo.git"


def test_schema_migrates_source_uri_onto_existing_projects_table(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE projects (id VARCHAR(36) PRIMARY KEY, name VARCHAR(300), "
            "root_path VARCHAR(1000), source_type VARCHAR(30), status VARCHAR(30), "
            "source_revision VARCHAR(64), tech_stack_json TEXT, last_scanned_at DATETIME, "
            "created_at DATETIME, updated_at DATETIME)"
        )

    database = Database(f"sqlite:///{path.as_posix()}")
    database.create_schema()

    with database.engine.connect() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(projects)")
        }
    assert "source_uri" in columns


def test_conversation_can_be_bound_to_project(tmp_path: Path) -> None:
    projects, conversations = make_repositories(tmp_path)
    project = projects.create(name="demo", root_path=str(tmp_path), source_type="local")

    conversation = conversations.create("项目问答", project_id=project.id)

    assert conversation.project_id == project.id
    assert [item.id for item in conversations.list(project_id=project.id)] == [conversation.id]


def test_conversation_message_preserves_comparison_metadata(tmp_path: Path) -> None:
    _, conversations = make_repositories(tmp_path)
    conversation = conversations.create("模型对比")

    conversations.add_message(
        conversation.id,
        role="assistant",
        content="模型对比结果",
        metadata={
            "type": "model_comparison",
            "items": [{"provider_name": "模型 A", "answer": "回答 A"}],
        },
    )

    message = conversations.list_messages(conversation.id)[0]
    assert message.metadata["type"] == "model_comparison"
    assert message.metadata["items"][0]["provider_name"] == "模型 A"


def test_project_use_case_rejects_missing_directory(tmp_path: Path) -> None:
    projects, _ = make_repositories(tmp_path)
    use_case = ProjectUseCase(projects)

    with pytest.raises(ValidationError, match="项目目录不存在"):
        use_case.create("missing", str(tmp_path / "missing"))


class FakeRemoteManager:
    def __init__(self, cache: Path) -> None:
        self.cache = cache
        self.updated = []
        self.removed = []

    def clone(self, url: str, *, expected_source: str | None = None):
        self.cache.mkdir(parents=True, exist_ok=True)
        return RemoteRepository(
            source_type=expected_source or "github",
            url=url.rstrip("/").removesuffix(".git") + ".git",
            owner="example",
            name="demo",
            cache_path=self.cache,
        )

    def update(self, path: str | Path):
        self.updated.append(Path(path))
        return ["remote_update_unavailable"]

    def remove(self, path: str | Path):
        self.removed.append(Path(path))


def test_project_use_case_creates_prepares_and_deletes_remote_project(tmp_path: Path) -> None:
    projects, _ = make_repositories(tmp_path)
    manager = FakeRemoteManager(tmp_path / "git-cache" / "github-demo")
    use_case = ProjectUseCase(projects, manager)

    project = use_case.create(
        "Remote demo",
        source_type="github",
        repository_url="https://github.com/example/demo",
    )

    assert project.source_type == "github"
    assert project.source_uri == "https://github.com/example/demo.git"
    assert project.root_path == str(manager.cache.resolve())
    assert use_case.prepare_for_scan(project.id) == ["remote_update_unavailable"]

    use_case.delete(project.id)

    assert manager.removed == [manager.cache.resolve()]
    assert projects.get(project.id) is None
