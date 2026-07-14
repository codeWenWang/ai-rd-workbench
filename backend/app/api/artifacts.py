from fastapi import APIRouter, Depends

from app.api.serializers import serialize
from app.dependencies import AppContainer, get_container


router = APIRouter(prefix="/api/projects/{project_id}/artifacts", tags=["artifacts"])


@router.get("")
def list_artifacts(project_id: str, container: AppContainer = Depends(get_container)):
    items = container.artifact_use_case.list(project_id)
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("/{artifact_type}")
def generate_artifact(
    project_id: str,
    artifact_type: str,
    container: AppContainer = Depends(get_container),
):
    return serialize(container.artifact_use_case.generate(project_id, artifact_type))


@router.get("/item/{artifact_id}")
def get_artifact(
    project_id: str,
    artifact_id: str,
    container: AppContainer = Depends(get_container),
):
    artifact = container.artifact_use_case.get(artifact_id)
    if artifact.project_id != project_id:
        from app.domain.errors import ResourceNotFound

        raise ResourceNotFound("artifact not found")
    return serialize(artifact)
