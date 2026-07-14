import asyncio

from app.domain.entities import (
    Citation,
    MessageRole,
    MessageStatus,
    ModelMessage,
    ResourceType,
)
from app.domain.errors import ExternalServiceError


class ChatUseCase:
    def __init__(
        self,
        conversations,
        graph,
        memories,
        *,
        model=None,
        retriever=None,
        project_retriever=None,
        model_gateway=None,
    ) -> None:
        self.conversations = conversations
        self.graph = graph
        self.memories = memories
        self.model = model
        self.retriever = retriever
        self.project_retriever = project_retriever
        self.model_gateway = model_gateway

    def create_session(self, project_id: str | None = None):
        return self.conversations.create("新对话", project_id=project_id)

    async def chat(self, message: str, session_id: str | None = None) -> dict:
        conversation = self.conversations.get(session_id) if session_id else None
        conversation = conversation or self.create_session()
        existing_messages = self.conversations.list_messages(conversation.id)
        if not existing_messages and conversation.title in {"New conversation", "新对话"}:
            conversation = self.conversations.rename(conversation.id, conversation_title(message))
        user_message = self.conversations.add_message(conversation.id, role="user", content=message,
                                                      status=MessageStatus.COMPLETED)
        assistant = self.conversations.add_message(conversation.id, role="assistant", content="",
                                                   status=MessageStatus.PENDING)
        try:
            result = await self.graph.ainvoke({"query": message, "retry_count": 0, "warnings": []})
            completed = self.conversations.update_message(
                assistant.id, content=result.get("answer", ""), status=MessageStatus.COMPLETED,
                citations=result.get("citations", []), warnings=result.get("warnings", []),
            )
            for candidate in result.get("memory_candidates", []):
                self.memories.create_candidate(title=candidate["title"], content=candidate["content"],
                                               kind=candidate["kind"], conversation_id=conversation.id,
                                               message_id=user_message.id)
            citations = [citation_to_dict(item) for item in completed.citations]
            return {"answer": completed.content, "session_id": conversation.id,
                    "sources": {"items": citations, "count": len(citations)},
                    "citations": citations, "warnings": completed.warnings}
        except Exception as exc:
            self.conversations.update_message(assistant.id, status=MessageStatus.FAILED,
                                              error_code=getattr(exc, "code", "chat_failed"),
                                              error_message=str(exc))
            raise

    async def stream_chat(
        self,
        message: str,
        session_id: str | None = None,
        *,
        project_id: str | None = None,
        model_id: str | None = None,
    ):
        conversation = self.conversations.get(session_id) if session_id else None
        conversation = conversation or self.create_session(project_id)
        existing_messages = self.conversations.list_messages(conversation.id)
        if not existing_messages and conversation.title in {"New conversation", "新对话"}:
            conversation = self.conversations.rename(
                conversation.id, conversation_title(message)
            )
        user_message = self.conversations.add_message(
            conversation.id,
            role="user",
            content=message,
            status=MessageStatus.COMPLETED,
        )
        assistant = self.conversations.add_message(
            conversation.id,
            role="assistant",
            content="",
            status=MessageStatus.PENDING,
        )
        yield {
            "event": "session",
            "data": {
                "session_id": conversation.id,
                "message_id": assistant.id,
                "project_id": conversation.project_id,
            },
        }
        answer_parts: list[str] = []
        try:
            yield {"event": "stage", "data": {"stage": "retrieving"}}
            context, warnings = await self._stream_context(
                message, conversation.project_id or project_id
            )
            prompt = _stream_prompt(message, context)
            yield {"event": "stage", "data": {"stage": "generating"}}
            messages = [ModelMessage(MessageRole.USER, prompt)]
            async for token in self._model_stream(model_id, messages):
                answer_parts.append(token)
                yield {"event": "token", "data": {"token": token, "model_id": model_id}}
            answer = "".join(answer_parts)
            citations = [_stream_citation(item) for item in context]
            completed = self.conversations.update_message(
                assistant.id,
                content=answer,
                status=MessageStatus.COMPLETED,
                citations=citations,
                warnings=warnings,
            )
            for warning in warnings:
                yield {"event": "warning", "data": {"warning": warning}}
            yield {
                "event": "citations",
                "data": [citation_to_dict(item) for item in citations],
            }
            self._create_stream_candidate(
                message, conversation.id, user_message.id
            )
            yield {
                "event": "done",
                "data": {
                    "ok": True,
                    "answer": completed.content,
                    "session_id": conversation.id,
                    "citations": [citation_to_dict(item) for item in citations],
                    "warnings": warnings,
                },
            }
        except asyncio.CancelledError:
            self.conversations.update_message(
                assistant.id,
                content="".join(answer_parts),
                status=MessageStatus.CANCELLED,
                error_code="generation_cancelled",
                error_message="generation cancelled",
            )
            raise
        except Exception as exc:
            self.conversations.update_message(
                assistant.id,
                content="".join(answer_parts),
                status=MessageStatus.FAILED,
                error_code=getattr(exc, "code", "chat_failed"),
                error_message=str(exc),
            )
            raise

    async def _stream_context(self, query: str, project_id: str | None):
        if project_id and self.project_retriever:
            result = await self.project_retriever.retrieve(project_id, query)
            return result.documents[:6], result.warnings
        if not self.retriever:
            return [], []
        knowledge, memory = await asyncio.gather(
            self.retriever.retrieve(query, ResourceType.KNOWLEDGE),
            self.retriever.retrieve(query, ResourceType.MEMORY),
        )
        return (
            knowledge.documents[:4] + memory.documents[:2],
            list(dict.fromkeys(knowledge.warnings + memory.warnings)),
        )

    async def _model_stream(self, model_id: str | None, messages):
        if model_id and self.model_gateway:
            async for token in self.model_gateway.stream(model_id, messages):
                yield token
            return
        if not self.model:
            raise ExternalServiceError("model service unavailable")
        async for token in self.model.astream(messages):
            yield token

    def _create_stream_candidate(
        self, message: str, conversation_id: str, message_id: str
    ) -> None:
        if not any(marker in message for marker in ("我偏好", "我喜欢", "请记住", "我的决定")):
            return
        self.memories.create_candidate(
            title="对话记忆建议",
            content=message,
            kind="preference",
            conversation_id=conversation_id,
            message_id=message_id,
        )


def citation_to_dict(citation):
    return {"chunk_id": citation.chunk_id, "title": citation.title, "excerpt": citation.excerpt,
            "page_number": citation.page_number, "category": citation.category,
            "resource_type": citation.resource_type, "relative_path": citation.relative_path,
            "start_line": citation.start_line, "end_line": citation.end_line}


def _stream_prompt(query, context) -> str:
    rendered = "\n\n".join(
        f"[{index}] {item.title or item.metadata.get('relative_path') or 'Source'}\n{item.content}"
        for index, item in enumerate(context, start=1)
    )
    return (
        "请用中文回答。优先依据提供的项目或知识上下文，不要编造源码事实。"
        "如果上下文不足，请明确说明。\n\n上下文：\n"
        + rendered
        + "\n\n问题：\n"
        + query
    )


def _stream_citation(item) -> Citation:
    metadata = item.metadata or {}
    return Citation(
        chunk_id=item.chunk_id,
        title=item.title or metadata.get("relative_path") or "Source",
        excerpt=item.content[:240],
        page_number=item.page_number,
        category=item.category,
        resource_type=item.resource_type.value,
        relative_path=metadata.get("relative_path"),
        start_line=metadata.get("start_line"),
        end_line=metadata.get("end_line"),
    )


def conversation_title(message: str, max_length: int = 24) -> str:
    title = " ".join(message.split()).strip(" ?？!！。,.，") or "新对话"
    if len(title) <= max_length:
        return title
    return title[:max_length - 1].rstrip() + "…"
