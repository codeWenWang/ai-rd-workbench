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


async def test_stream_chat_emits_exact_model_chunks_and_persists_answer(tmp_path) -> None:
    use_case, conversations, _, _ = make_use_case(tmp_path)

    events = [event async for event in use_case.stream_chat("测试流式")]

    tokens = [item["data"]["token"] for item in events if item["event"] == "token"]
    assert tokens == ["第一段", "第二段"]
    session_id = next(item["data"]["session_id"] for item in events if item["event"] == "session")
    messages = conversations.list_messages(session_id)
    assert messages[-1].content == "第一段第二段"
    assert messages[-1].status is MessageStatus.COMPLETED


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
