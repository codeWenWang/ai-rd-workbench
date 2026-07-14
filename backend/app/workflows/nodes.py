from app.domain.entities import Citation, MemoryKind, ModelMessage, MessageRole, ResourceType


_PERSONAL_MEMORY_MARKERS = (
    "我偏好",
    "我的偏好",
    "我喜欢",
    "我习惯",
    "我常用",
    "我之前",
    "我说过",
    "记得我",
    "关于我",
    "我的决定",
    "my preference",
    "i prefer",
)


def _is_personal_memory_query(query: str) -> bool:
    normalized = query.strip().casefold()
    return any(marker in normalized for marker in _PERSONAL_MEMORY_MARKERS)


def make_nodes(model, retriever):
    async def retrieve_context(state):
        query = state.get("rewritten_query") or state["query"]
        knowledge = await retriever.retrieve(query, ResourceType.KNOWLEDGE)
        memory = await retriever.retrieve(query, ResourceType.MEMORY)
        if _is_personal_memory_query(state["query"]):
            context = memory.documents[:4] + knowledge.documents[:2]
        else:
            context = knowledge.documents[:4] + memory.documents[:2]
        return {
            "context": context,
            "warnings": list(dict.fromkeys(knowledge.warnings + memory.warnings)),
        }

    def evaluate_context(state):
        if state.get("context"):
            return "generate"
        if state.get("retry_count", 0) < 1:
            return "retry"
        return "insufficient"

    async def rewrite_query(state):
        return {
            "rewritten_query": state["query"] + " 相关背景 具体事实",
            "retry_count": 1,
        }

    async def generate_answer(state):
        context = state.get("context", [])[:6]
        rendered = "\n\n".join(
            f"[{index}][{'LONG_TERM_MEMORY' if item.resource_type is ResourceType.MEMORY else 'KNOWLEDGE'}] "
            f"{item.content}"
            for index, item in enumerate(context, 1)
        )
        prompt = (
            "Answer the user in Chinese. Use only helpful retrieved context when relevant. "
            "For questions about the user's preferences, habits, decisions, or previously stated facts, "
            "prioritize LONG_TERM_MEMORY and do not replace it with project KNOWLEDGE. "
            "Do not invent sources.\n\nContext:\n"
            + rendered
            + "\n\nQuestion:\n"
            + state["query"]
        )
        answer = await model.ainvoke([ModelMessage(MessageRole.USER, prompt)])
        citations = [
            Citation(
                item.chunk_id,
                item.title or "Source",
                item.content[:240],
                item.page_number,
                item.category,
            )
            for item in context
        ]
        return {"answer": answer, "citations": citations}

    async def insufficient(state):
        prompt = "请直接回答；如果信息不足，请明确说明不确定。问题：" + state["query"]
        answer = await model.ainvoke([ModelMessage(MessageRole.USER, prompt)])
        return {"answer": answer, "citations": []}

    async def propose_memories(state):
        query = state["query"]
        markers = ("我偏好", "我喜欢", "请记住", "我的决定")
        if not any(marker in query for marker in markers):
            return {"memory_candidates": []}
        return {
            "memory_candidates": [
                {
                    "title": "对话记忆建议",
                    "content": query,
                    "kind": MemoryKind.PREFERENCE.value,
                }
            ]
        }

    return retrieve_context, evaluate_context, rewrite_query, generate_answer, insufficient, propose_memories
