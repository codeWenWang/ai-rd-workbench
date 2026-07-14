from pathlib import Path

from app.application.models import ModelProviderUseCase
from app.domain.entities import MessageRole, ModelMessage
from app.infrastructure.db.repositories import SqliteModelProviderRepository
from app.infrastructure.db.session import Database
from app.infrastructure.llm.gateway import ModelGateway
from app.infrastructure.security.secrets import LocalSecretStore


class RecordingModel:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        return self.answer

    async def astream(self, messages):
        self.messages = messages
        yield self.answer


async def test_compare_uses_identical_messages_for_both_models() -> None:
    first = RecordingModel("A")
    second = RecordingModel("B")
    gateway = ModelGateway({"first": first, "second": second})
    messages = [ModelMessage(MessageRole.USER, "同一个问题")]

    result = await gateway.compare(messages, ["first", "second"])

    assert first.messages is messages
    assert second.messages is messages
    assert [item.model_id for item in result] == ["first", "second"]
    assert [item.answer for item in result] == ["A", "B"]


async def test_compare_isolates_one_model_failure() -> None:
    class BrokenModel(RecordingModel):
        async def ainvoke(self, messages):
            raise RuntimeError("api_key=secret-value")

    gateway = ModelGateway({"good": RecordingModel("正常"), "bad": BrokenModel("")})

    result = await gateway.compare(
        [ModelMessage(MessageRole.USER, "测试")], ["good", "bad"]
    )

    assert result[0].answer == "正常"
    assert result[1].error == "模型调用失败"
    assert "secret-value" not in result[1].error


def test_local_secret_store_does_not_write_plaintext_key(tmp_path: Path) -> None:
    store = LocalSecretStore(tmp_path)

    store.set("provider-1", "sk-plain-secret")

    assert store.get("provider-1") == "sk-plain-secret"
    assert "sk-plain-secret" not in (tmp_path / "model-secrets.json").read_text(encoding="utf-8")


def test_model_provider_metadata_never_exposes_api_key(tmp_path: Path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'models.db').as_posix()}")
    database.create_schema()
    secrets = LocalSecretStore(tmp_path / "secrets")
    use_case = ModelProviderUseCase(
        SqliteModelProviderRepository(database.session_factory), secrets
    )

    provider = use_case.create(
        name="DeepSeek",
        provider_type="openai_compatible",
        base_url="https://example.test/v1",
        model_name="deepseek-chat",
        api_key="sk-provider-secret",
    )

    assert provider.has_api_key is True
    assert not hasattr(provider, "api_key")
    assert use_case.list()[0].model_name == "deepseek-chat"


def test_model_provider_can_be_edited_without_replacing_existing_key(tmp_path: Path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'models.db').as_posix()}")
    database.create_schema()
    secrets = LocalSecretStore(tmp_path / "secrets")
    use_case = ModelProviderUseCase(
        SqliteModelProviderRepository(database.session_factory), secrets
    )
    provider = use_case.create(
        name="DeepSeek",
        provider_type="openai_compatible",
        base_url="https://example.test/v1",
        model_name="deepseek-chat",
        api_key="sk-provider-secret",
    )

    updated = use_case.update(
        provider.id,
        name="DeepSeek V4",
        model_name="deepseek-v4",
        api_key="",
    )

    assert updated.name == "DeepSeek V4"
    assert updated.model_name == "deepseek-v4"
    assert updated.has_api_key is True
    assert secrets.get(provider.secret_ref) == "sk-provider-secret"
