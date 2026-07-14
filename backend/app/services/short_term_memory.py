import json
import uuid

import redis

from app.config import settings
from app.services.llm_service import llm_service


class ShortTermMemoryService:
    """会话短期记忆：滑动窗口 + 摘要压缩，存储于 Redis。"""

    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
        )
        self.window_size = settings.short_term_window_size
        self.summary_threshold = settings.short_term_summary_threshold

    def _messages_key(self, session_id: str) -> str:
        return f"stm:{session_id}:messages"

    def _summary_key(self, session_id: str) -> str:
        return f"stm:{session_id}:summary"

    def add_message(self, session_id: str, role: str, content: str) -> None:
        msg = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        key = self._messages_key(session_id)
        self.redis.rpush(key, msg)
        self.redis.expire(key, 86400 * 7)

        length = self.redis.llen(key)
        if length > self.summary_threshold:
            self._compress(session_id)

        if length > self.window_size:
            self.redis.ltrim(key, -self.window_size, -1)

    def _compress(self, session_id: str) -> None:
        messages_key = self._messages_key(session_id)
        raw_messages = self.redis.lrange(messages_key, 0, -1)
        if len(raw_messages) <= self.summary_threshold:
            return

        to_summarize = raw_messages[: len(raw_messages) - self.window_size + 2]
        if not to_summarize:
            return

        conversation_parts = []
        for raw in to_summarize:
            msg = json.loads(raw)
            conversation_parts.append(f"{msg['role']}: {msg['content']}")

        existing_summary = self.redis.get(self._summary_key(session_id)) or ""
        conversation = existing_summary + "\n" + "\n".join(conversation_parts)
        new_summary = llm_service.summarize(conversation)

        self.redis.set(self._summary_key(session_id), new_summary, ex=86400 * 7)
        keep_count = max(1, len(raw_messages) - len(to_summarize))
        self.redis.ltrim(messages_key, -keep_count, -1)

    def get_context(self, session_id: str) -> str:
        summary = self.redis.get(self._summary_key(session_id)) or ""
        messages = self.redis.lrange(self._messages_key(session_id), 0, -1)

        parts = []
        if summary:
            parts.append(f"[历史摘要]\n{summary}")
        for raw in messages:
            msg = json.loads(raw)
            parts.append(f"{msg['role']}: {msg['content']}")
        return "\n".join(parts)

    def get_recent_messages(self, session_id: str) -> list[dict]:
        messages = self.redis.lrange(self._messages_key(session_id), 0, -1)
        return [json.loads(m) for m in messages]

    def clear(self, session_id: str) -> None:
        self.redis.delete(self._messages_key(session_id))
        self.redis.delete(self._summary_key(session_id))

    def create_session(self) -> str:
        return str(uuid.uuid4())


short_term_memory = ShortTermMemoryService()
