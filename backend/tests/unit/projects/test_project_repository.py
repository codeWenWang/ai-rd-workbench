from pathlib import Path

import pytest

from app.application.projects import ProjectUseCase
from app.domain.errors import ValidationError
from app.infrastructure.db.repositories import (
    SqliteConversationRepository,
    SqliteProjectRepository,
)
from app.infrastructure.db.session import Database


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
