from app.application.chat import ChatUseCase
from app.domain.entities import MessageStatus, RetrievalResult
from app.infrastructure.db.repositories import (
    SqliteConversationRepository,
    SqliteProjectRepository,
)
from app.infrastructure.db.session import Database


class ExactStreamingModel:
    async def ainvoke(self, messages):
        return "第一段第二段"

    async def astream(self, messages):
        yield "第一段"
        yield "第二段"


class StreamUnavailableModel:
    async def ainvoke(self, messages):
        return "普通调用恢复成功"

    async def astream(self, messages):
        raise RuntimeError("temporary stream failure")
        yield


class EmptyRetriever:
    def __init__(self):
        self.calls = []

    async def retrieve(self, query, resource_type):
        self.calls.append((query, resource_type))
        return RetrievalResult()


class RecordingProjectRetriever:
    def __init__(self):
        self.calls = []

    async def retrieve(self, project_id, query):
        self.calls.append((project_id, query))
        return RetrievalResult()


class NoopMemories:
    def create_candidate(self, **kwargs):
        return None


def make_use_case(tmp_path, *, project_retriever=None):
    database = Database(f"sqlite:///{(tmp_path / 'stream.db').as_posix()}")
    database.create_schema()
    conversations = SqliteConversationRepository(database.session_factory)
    retriever = EmptyRetriever()
    use_case = ChatUseCase(
        conversations,
        graph=None,
        memories=NoopMemories(),
        model=ExactStreamingModel(),
        retriever=retriever,
        project_retriever=project_retriever,
    )
    return (
        use_case,
        conversations,
        SqliteProjectRepository(database.session_factory),
        retriever,
    )


async def test_stream_chat_falls_back_to_regular_model_call_before_first_token(tmp_path) -> None:
    use_case, conversations, _, _ = make_use_case(tmp_path)
    use_case.model = StreamUnavailableModel()

    events = [event async for event in use_case.stream_chat("测试降级")]

    tokens = [item["data"]["token"] for item in events if item["event"] == "token"]
    assert tokens == ["普通调用恢复成功"]
    session_id = next(item["data"]["session_id"] for item in events if item["event"] == "session")
    assert conversations.list_messages(session_id)[-1].content == "普通调用恢复成功"


async def test_stream_chat_emits_exact_model_chunks_and_persists_answer(tmp_path) -> None:
    use_case, conversations, _, _ = make_use_case(tmp_path)

    events = [event async for event in use_case.stream_chat("测试流式")]

    tokens = [item["data"]["token"] for item in events if item["event"] == "token"]
    assert tokens == ["第一段", "第二段"]
    session_id = next(item["data"]["session_id"] for item in events if item["event"] == "session")
    messages = conversations.list_messages(session_id)
    assert messages[-1].content == "第一段第二段"
    assert messages[-1].status is MessageStatus.COMPLETED


async def test_stream_chat_retry_reuses_failed_assistant_message(tmp_path) -> None:
    use_case, conversations, _, _ = make_use_case(tmp_path)
    conversation = use_case.create_session()
    user = conversations.add_message(
        conversation.id,
        role="user",
        content="重试这个问题",
        status=MessageStatus.COMPLETED,
    )
    failed = conversations.add_message(
        conversation.id,
        role="assistant",
        content="",
        status=MessageStatus.FAILED,
    )
    conversations.update_message(
        failed.id,
        error_code="chat_failed",
        error_message="temporary failure",
    )

    events = [
        event async for event in use_case.stream_chat(
            user.content,
            session_id=conversation.id,
            retry_message_id=failed.id,
        )
    ]

    messages = conversations.list_messages(conversation.id)
    assert len(messages) == 2
    assert messages[-1].id == failed.id
    assert messages[-1].status is MessageStatus.COMPLETED
    assert messages[-1].content == "第一段第二段"
    assert next(item for item in events if item["event"] == "session")["data"]["message_id"] == failed.id


async def test_stream_chat_binds_new_conversation_to_project(tmp_path) -> None:
    use_case, conversations, projects, _ = make_use_case(tmp_path)
    project = projects.create(name="demo", root_path=str(tmp_path))

    events = [
        event async for event in use_case.stream_chat(
            "项目问题", project_id=project.id
        )
    ]

    session_id = next(item["data"]["session_id"] for item in events if item["event"] == "session")
    assert conversations.get(session_id).project_id == project.id


async def test_existing_daily_conversation_ignores_requested_project_context(tmp_path) -> None:
    project_retriever = RecordingProjectRetriever()
    use_case, conversations, projects, retriever = make_use_case(
        tmp_path, project_retriever=project_retriever
    )
    project = projects.create(name="demo", root_path=str(tmp_path))
    conversation = use_case.create_session()

    events = [
        event async for event in use_case.stream_chat(
            "日常问题",
            session_id=conversation.id,
            project_id=project.id,
        )
    ]

    assert next(item for item in events if item["event"] == "session")["data"]["project_id"] is None
    assert conversations.get(conversation.id).project_id is None
    assert project_retriever.calls == []
    assert len(retriever.calls) == 2


def test_create_session_reuses_latest_empty_conversation_and_refreshes_time(tmp_path) -> None:
    use_case, conversations, projects, _ = make_use_case(tmp_path)
    project = projects.create(name="demo", root_path=str(tmp_path))
    first = use_case.create_session(project.id)
    original_created_at = first.created_at

    reused = use_case.create_session(project.id)

    assert reused.id == first.id
    assert reused.project_id == project.id
    assert reused.created_at >= original_created_at
    assert conversations.list_messages(reused.id) == []
    assert len(conversations.list(project_id=project.id)) == 1


def test_create_session_does_not_reuse_conversation_with_messages(tmp_path) -> None:
    use_case, conversations, _, _ = make_use_case(tmp_path)
    first = use_case.create_session()
    conversations.add_message(
        first.id, role="user", content="已有消息", status=MessageStatus.COMPLETED
    )

    created = use_case.create_session()

    assert created.id != first.id
    assert len(conversations.list()) == 2


def test_create_session_does_not_skip_latest_conversation_to_reuse_older_empty(tmp_path) -> None:
    use_case, conversations, _, _ = make_use_case(tmp_path)
    older_empty = use_case.create_session()
    latest = conversations.create("已有对话")
    conversations.add_message(
        latest.id, role="user", content="已有消息", status=MessageStatus.COMPLETED
    )

    created = use_case.create_session()

    assert created.id not in {older_empty.id, latest.id}
    assert len(conversations.list()) == 3
