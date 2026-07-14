import sys
import types

from app.config import Settings
from app.infrastructure.llm.dashscope import DashScopeEmbeddingModel


def test_dashscope_embeddings_send_raw_text(monkeypatch) -> None:
    captured = {}

    class FakeOpenAIEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "langchain_openai",
        types.SimpleNamespace(OpenAIEmbeddings=FakeOpenAIEmbeddings),
    )
    adapter = DashScopeEmbeddingModel(Settings(dashscope_api_key="test-key"))

    adapter._get_client()

    assert captured["check_embedding_ctx_length"] is False
