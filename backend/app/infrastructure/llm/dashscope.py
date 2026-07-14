from collections.abc import AsyncIterator

from app.config import Settings
from app.domain.entities import ModelMessage
from app.domain.errors import ExternalServiceError


class DashScopeChatModel:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None

    def _get_client(self):
        if not self.settings.dashscope_api_key:
            raise ExternalServiceError("DashScope API key is not configured")
        if self._client is None:
            from langchain_openai import ChatOpenAI

            self._client = ChatOpenAI(
                api_key=self.settings.dashscope_api_key,
                base_url=self.settings.dashscope_base_url,
                model=self.settings.llm_model,
                temperature=0.2,
            )
        return self._client

    async def ainvoke(self, messages: list[ModelMessage]) -> str:
        try:
            response = await self._get_client().ainvoke([(item.role.value, item.content) for item in messages])
            return str(response.content)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError("model service unavailable") from exc

    async def astream(self, messages: list[ModelMessage]) -> AsyncIterator[str]:
        try:
            async for response in self._get_client().astream([(item.role.value, item.content) for item in messages]):
                if response.content:
                    yield str(response.content)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError("model streaming service unavailable") from exc


class DashScopeEmbeddingModel:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None

    def _get_client(self):
        if not self.settings.dashscope_api_key:
            raise ExternalServiceError("DashScope API key is not configured")
        if self._client is None:
            from langchain_openai import OpenAIEmbeddings

            self._client = OpenAIEmbeddings(
                api_key=self.settings.dashscope_api_key,
                base_url=self.settings.dashscope_base_url,
                model=self.settings.embedding_model,
                dimensions=self.settings.embedding_dimension,
                check_embedding_ctx_length=False,
            )
        return self._client

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return await self._get_client().aembed_documents(texts)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError("embedding service unavailable") from exc

    async def embed_query(self, text: str) -> list[float]:
        try:
            return await self._get_client().aembed_query(text)
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError("embedding service unavailable") from exc
