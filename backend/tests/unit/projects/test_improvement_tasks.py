import asyncio
import json

from app.application.improvement_tasks import ImprovementTaskUseCase
from app.application.project_analysis import ProjectAnalysisUseCase
from app.infrastructure.db.repositories import (
    SqliteImprovementTaskRepository,
    SqliteProjectAnalysisRepository,
    SqliteProjectRepository,
)
from app.infrastructure.db.session import Database
from app.infrastructure.projects.parsers import ParserRegistry
from app.infrastructure.projects.scanner import LocalProjectScanner


class FixedModel:
    def __init__(self, answers):
        self.answers = iter(answers)

    async def ainvoke(self, _messages):
        return next(self.answers)


def make_use_case(tmp_path, answers):
    database = Database(f"sqlite:///{(tmp_path / 'tasks.db').as_posix()}")
    database.create_schema()
    projects = SqliteProjectRepository(database.session_factory)
    analysis = SqliteProjectAnalysisRepository(database.session_factory)
    tasks = SqliteImprovementTaskRepository(database.session_factory)
    scanner = ProjectAnalysisUseCase(projects, analysis, LocalProjectScanner(), ParserRegistry())
    return projects, analysis, tasks, scanner, ImprovementTaskUseCase(
        tasks,
        projects,
        analysis,
        FixedModel(answers),
        project_analysis_use_case=scanner,
    )


def test_create_task_persists_plan_and_review_detects_modified_files(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    source = root / "main.py"
    source.write_text("def list_items():\n    return []\n", encoding="utf-8")
    plan = {
        "title": "增加任务筛选",
        "summary": "增加筛选入口",
        "steps": [{"id": "step-1", "title": "修改接口", "description": "增加筛选参数", "affected_files": ["main.py"]}],
        "affected_files": [{"path": "main.py", "reason": "接口入口"}],
        "risks": [],
        "acceptance_criteria": ["接口支持筛选"],
        "agent_prompt": "先阅读 main.py，再增加筛选参数。",
    }
    review = {
        "summary": "已找到修改并满足标准",
        "criteria": [{"criterion": "接口支持筛选", "status": "passed", "evidence": "main.py:1"}],
        "findings": [],
        "next_actions": [],
    }
    projects, analysis, tasks, scanner, use_case = make_use_case(
        tmp_path, [json.dumps(plan, ensure_ascii=False), json.dumps(review, ensure_ascii=False)]
    )
    project = projects.create(name="demo", root_path=str(root))
    scanner.scan(project.id)
    task = asyncio.run(use_case.create(project_id=project.id, goal="增加任务筛选"))
    assert task.title == "增加任务筛选"
    assert task.baseline_hashes["main.py"]
    source.write_text("def list_items(status=None):\n    return []\n", encoding="utf-8")
    reviewed = asyncio.run(use_case.review(task.id))
    assert reviewed.status == "completed"
    assert reviewed.review["changed_files"]["modified"] == ["main.py"]
