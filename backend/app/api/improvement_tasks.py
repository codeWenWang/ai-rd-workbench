from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.serializers import serialize
from app.dependencies import AppContainer, get_container


router = APIRouter(prefix="/api/improvement-tasks", tags=["improvement-tasks"])


class TaskCreate(BaseModel):
    project_id: str
    goal: str = Field(min_length=2, max_length=4000)
    title: str = Field(default="", max_length=300)
    model_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    status: Literal["planned", "in_progress", "needs_review", "completed"] | None = None
    completed_step_ids: list[str] | None = None
    agent_prompt: str | None = Field(default=None, max_length=30000)


class ReviewRequest(BaseModel):
    model_id: str | None = None


@router.get("")
def list_tasks(
    project_id: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
):
    items = container.improvement_task_use_case.list(project_id=project_id)
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("")
async def create_task(
    payload: TaskCreate,
    container: AppContainer = Depends(get_container),
):
    task = await container.improvement_task_use_case.create(
        project_id=payload.project_id,
        goal=payload.goal,
        title=payload.title,
        model_id=payload.model_id,
    )
    return serialize(task)


@router.get("/{task_id}")
def get_task(task_id: str, container: AppContainer = Depends(get_container)):
    return serialize(container.improvement_task_use_case.get(task_id))


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    payload: TaskUpdate,
    container: AppContainer = Depends(get_container),
):
    return serialize(container.improvement_task_use_case.update(
        task_id,
        title=payload.title,
        status=payload.status,
        completed_step_ids=payload.completed_step_ids,
        agent_prompt=payload.agent_prompt,
    ))


@router.post("/{task_id}/review")
async def review_task(
    task_id: str,
    payload: ReviewRequest,
    container: AppContainer = Depends(get_container),
):
    task = await container.improvement_task_use_case.review(
        task_id, model_id=payload.model_id
    )
    return serialize(task)


@router.delete("/{task_id}")
def delete_task(task_id: str, container: AppContainer = Depends(get_container)):
    container.improvement_task_use_case.delete(task_id)
    return {"success": True}
