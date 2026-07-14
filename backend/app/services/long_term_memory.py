from app.config import settings
from app.services.document_processor import extract_pdf_text, semantic_chunk
from app.services.llm_service import llm_service
from app.services.pinecone_store import pinecone_store


class LongTermMemoryService:
    """会话长期记忆：主动录入 + 语义相似度召回。"""

    def ingest_text(self, session_id: str, text: str, title: str = "") -> dict:
        chunks = semantic_chunk(text)
        if not chunks:
            return {"success": False, "message": "文本内容为空", "count": 0}

        doc_ids = pinecone_store.upsert_documents(
            chunks,
            namespace=pinecone_store.NS_LTM,
            metadata_base={
                "session_id": session_id,
                "source_type": "text",
                "title": title or "文本记忆",
            },
        )
        return {"success": True, "message": f"成功录入 {len(doc_ids)} 条记忆片段", "count": len(doc_ids)}

    def ingest_pdf(self, session_id: str, file_bytes: bytes, filename: str) -> dict:
        text = extract_pdf_text(file_bytes)
        if not text.strip():
            return {"success": False, "message": "PDF 中未提取到文本", "count": 0}

        chunks = semantic_chunk(text)
        doc_ids = pinecone_store.upsert_documents(
            chunks,
            namespace=pinecone_store.NS_LTM,
            metadata_base={
                "session_id": session_id,
                "source_type": "pdf",
                "title": filename,
            },
        )
        return {
            "success": True,
            "message": f"PDF '{filename}' 成功录入 {len(doc_ids)} 条记忆片段",
            "count": len(doc_ids),
        }

    def recall(self, session_id: str, query: str, top_k: int = 3) -> str:
        rewritten = llm_service.rewrite_query(query)
        results = pinecone_store.hybrid_search(rewritten, pinecone_store.NS_LTM, top_k)

        session_results = [
            r for r in results if r.get("metadata", {}).get("session_id") == session_id
        ]
        if not session_results:
            session_results = pinecone_store.vector_search(
                rewritten, pinecone_store.NS_LTM, top_k
            )
            session_results = [
                r for r in session_results if r.get("metadata", {}).get("session_id") == session_id
            ]

        if not session_results:
            return ""

        parts = []
        for i, r in enumerate(session_results, 1):
            title = r.get("metadata", {}).get("title", "记忆")
            parts.append(f"{i}. [{title}] {r['text']}")
        return "\n".join(parts)


long_term_memory = LongTermMemoryService()
