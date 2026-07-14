from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.serializers import serialize
from app.dependencies import AppContainer, get_container


router = APIRouter(prefix="/api/model-providers", tags=["models"])
models_router = APIRouter(prefix="/api/models", tags=["models"])


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    provider_type: str
    base_url: str = Field(min_length=1, max_length=1000)
    model_name: str = Field(min_length=1, max_length=300)
    api_key: str = Field(min_length=1, max_length=2000)
    is_default: bool = False


class ProviderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    provider_type: str | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=1000)
    model_name: str | None = Field(default=None, min_length=1, max_length=300)
    api_key: str | None = Field(default=None, max_length=2000)
    is_default: bool | None = None


class ModelCompareRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    model_ids: list[str] = Field(min_length=1, max_length=2)
    project_id: str | None = None
    session_id: str | None = None


@router.get("")
def list_providers(container: AppContainer = Depends(get_container)):
    items = container.model_provider_use_case.list()
    return {"items": [serialize(item) for item in items], "total": len(items)}


@router.post("")
def create_provider(payload: ProviderCreate, container: AppContainer = Depends(get_container)):
    provider = container.model_provider_use_case.create(**payload.model_dump())
    _reset_model_cache(container)
    return serialize(provider)


@router.patch("/{provider_id}")
def update_provider(
    provider_id: str,
    payload: ProviderPatch,
    container: AppContainer = Depends(get_container),
):
    provider = container.model_provider_use_case.update(
        provider_id,
        **payload.model_dump(exclude_unset=True),
    )
    _reset_model_cache(container)
    return serialize(provider)


@router.delete("/{provider_id}")
def delete_provider(provider_id: str, container: AppContainer = Depends(get_container)):
    container.model_provider_use_case.delete(provider_id)
    _reset_model_cache(container)
    return {"success": True}


def _reset_model_cache(container: AppContainer) -> None:
    container.__dict__.pop("model_gateway", None)
    container.__dict__.pop("chat_use_case", None)


@models_router.post("/compare")
async def compare_models(
    payload: ModelCompareRequest,
    container: AppContainer = Depends(get_container),
):
    providers = {
        item.id: {
            "provider_name": item.name,
            "model_name": item.model_name,
        }
        for item in container.model_provider_use_case.list()
    }
    result = await container.chat_use_case.compare_models(
        payload.message,
        payload.model_ids,
        project_id=payload.project_id,
        session_id=payload.session_id,
        model_labels=providers,
    )
    return {
        "items": result["items"],
        "citations": [serialize(item) for item in result["citations"]],
        "warnings": result["warnings"],
        "session_id": result["session_id"],
        "message_id": result["message_id"],
    }
