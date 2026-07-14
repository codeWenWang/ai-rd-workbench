from app.domain.errors import ResourceNotFound, ValidationError
from app.infrastructure.llm.gateway import OpenAICompatibleChatModel


class ModelProviderUseCase:
    def __init__(self, providers, secrets) -> None:
        self.providers = providers
        self.secrets = secrets

    def create(
        self,
        *,
        name: str,
        provider_type: str,
        base_url: str,
        model_name: str,
        api_key: str,
        is_default: bool = False,
    ):
        if provider_type not in {"dashscope", "openai_compatible"}:
            raise ValidationError("不支持的模型供应商类型")
        if not base_url.strip() or not model_name.strip() or not api_key.strip():
            raise ValidationError("模型地址、模型名称和 API Key 不能为空")
        secret_ref = f"provider-{self._next_reference()}"
        self.secrets.set(secret_ref, api_key.strip())
        provider = self.providers.create(
            name=name.strip() or model_name.strip(),
            provider_type=provider_type,
            base_url=base_url.strip().rstrip("/"),
            model_name=model_name.strip(),
            secret_ref=secret_ref,
            is_default=is_default,
        )
        return self._public(provider)

    def ensure_dashscope_default(self, settings) -> None:
        if self.providers.list() or not settings.dashscope_api_key:
            return
        self.create(
            name="通义千问",
            provider_type="dashscope",
            base_url=settings.dashscope_base_url,
            model_name=settings.llm_model,
            api_key=settings.dashscope_api_key,
            is_default=True,
        )

    def list(self):
        return [self._public(item) for item in self.providers.list()]

    def get(self, provider_id: str):
        provider = self.providers.get(provider_id)
        if not provider:
            raise ResourceNotFound("model provider not found")
        return self._public(provider)

    def delete(self, provider_id: str) -> None:
        provider = self.providers.get(provider_id)
        if not provider:
            raise ResourceNotFound("model provider not found")
        self.providers.delete(provider_id)
        self.secrets.delete(provider.secret_ref)

    def build_model(self, provider_id: str):
        provider = self.providers.get(provider_id)
        if not provider:
            raise ResourceNotFound("model provider not found")
        api_key = self.secrets.get(provider.secret_ref)
        if not api_key:
            raise ValidationError("模型 API Key 未配置")
        return OpenAICompatibleChatModel(
            api_key=api_key,
            base_url=provider.base_url,
            model=provider.model_name,
        )

    def register_all(self, gateway) -> None:
        for provider in self.providers.list(enabled_only=True):
            gateway.register(provider.id, self.build_model(provider.id))

    def _public(self, provider):
        provider.has_api_key = self.secrets.has(provider.secret_ref)
        return provider

    def _next_reference(self) -> str:
        import uuid

        return str(uuid.uuid4())
