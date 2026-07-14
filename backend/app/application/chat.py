from app.domain.entities import MessageStatus


class ChatUseCase:
    def __init__(self, conversations, graph, memories) -> None:
        self.conversations = conversations
        self.graph = graph
        self.memories = memories

    def create_session(self):
        return self.conversations.create("新对话")

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


def citation_to_dict(citation):
    return {"chunk_id": citation.chunk_id, "title": citation.title, "excerpt": citation.excerpt,
            "page_number": citation.page_number, "category": citation.category}


def conversation_title(message: str, max_length: int = 24) -> str:
    title = " ".join(message.split()).strip(" ?？!！。,.，") or "新对话"
    if len(title) <= max_length:
        return title
    return title[:max_length - 1].rstrip() + "…"
