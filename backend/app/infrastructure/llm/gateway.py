import asyncio
from collections.abc import AsyncIterator
from time import perf_counter

from app.domain.entities import ModelComparisonResult, ModelMessage
from app.domain.errors import ExternalServiceError, ValidationError


class ModelGateway:
    def __init__(self, models: dict[str, object] | None = None) -> None:
        self.models = models or {}

    def register(self, model_id: str, model) -> None:
        self.models[model_id] = model

    def get(self, model_id: str):
        model = self.models.get(model_id)
        if not model:
            raise ValidationError("模型配置不存在")
        return model

    async def invoke(self, model_id: str, messages: list[ModelMessage]) -> str:
        return await self.get(model_id).ainvoke(messages)

    async def stream(
        self, model_id: str, messages: list[ModelMessage]
    ) -> AsyncIterator[str]:
        async for token in self.get(model_id).astream(messages):
            yield token

    async def compare(
        self, messages: list[ModelMessage], model_ids: list[str]
    ) -> list[ModelComparisonResult]:
        if not 1 <= len(model_ids) <= 2:
            raise ValidationError("模型对比最多选择两个模型")
        return list(await asyncio.gather(*[
            self._invoke_one(model_id, messages) for model_id in model_ids
        ]))

    async def _invoke_one(
        self, model_id: str, messages: list[ModelMessage]
    ) -> ModelComparisonResult:
        started = perf_counter()
        try:
            answer = await self.invoke(model_id, messages)
            return ModelComparisonResult(
                model_id=model_id,
                answer=answer,
                latency_ms=int((perf_counter() - started) * 1000),
            )
        except Exception:
            return ModelComparisonResult(
                model_id=model_id,
                error="模型调用失败",
                latency_ms=int((perf_counter() - started) * 1000),
            )


class OpenAICompatibleChatModel:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self._client = None

    def _get_client(self):
        if not self.api_key:
            raise ExternalServiceError("模型 API Key 未配置")
        if self._client is None:
            from langchain_openai import ChatOpenAI

            self._client = ChatOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                temperature=self.temperature,
            )
        return self._client

    async def ainvoke(self, messages: list[ModelMessage]) -> str:
        try:
            response = await self._get_client().ainvoke(
                [(item.role.value, item.content) for item in messages]
            )
            return str(response.content)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError("模型服务不可用") from exc

    async def astream(self, messages: list[ModelMessage]) -> AsyncIterator[str]:
        try:
            async for response in self._get_client().astream(
                [(item.role.value, item.content) for item in messages]
            ):
                if response.content:
                    yield str(response.content)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError("模型流式服务不可用") from exc
