from app.services.llm_service import llm_service
from app.services.long_term_memory import long_term_memory
from app.services.rag_service import rag_service
from app.services.short_term_memory import short_term_memory


class ChatService:
    def chat(self, session_id: str, message: str) -> dict:
        short_context = short_term_memory.get_context(session_id)
        ltm_context = long_term_memory.recall(session_id, message)
        rag_context = rag_service.retrieve(message, short_context)

        answer = llm_service.generate_answer(
            query=message,
            rag_context=rag_context,
            long_term_memory=ltm_context,
            short_term_context=short_context,
        )

        short_term_memory.add_message(session_id, "user", message)
        short_term_memory.add_message(session_id, "assistant", answer)

        return {
            "answer": answer,
            "session_id": session_id,
            "sources": {
                "rag_used": bool(rag_context),
                "ltm_used": bool(ltm_context),
            },
        }


chat_service = ChatService()
