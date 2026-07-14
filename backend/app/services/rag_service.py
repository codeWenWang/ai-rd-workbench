from app.config import settings
from app.services.document_processor import extract_pdf_text, semantic_chunk
from app.services.llm_service import llm_service
from app.services.pinecone_store import pinecone_store


class RAGService:
    """RAG 召回：查询改写 + 语义分块 + BM25/向量混合检索。"""

    def ingest_text(self, text: str, title: str = "", category: str = "general") -> dict:
        chunks = semantic_chunk(text)
        if not chunks:
            return {"success": False, "message": "文本内容为空", "count": 0}

        doc_ids = pinecone_store.upsert_documents(
            chunks,
            namespace=pinecone_store.NS_RAG,
            metadata_base={"title": title or "知识文档", "category": category, "source_type": "text"},
        )
        return {"success": True, "message": f"成功入库 {len(doc_ids)} 个知识片段", "count": len(doc_ids)}

    def ingest_pdf(self, file_bytes: bytes, filename: str, category: str = "general") -> dict:
        text = extract_pdf_text(file_bytes)
        if not text.strip():
            return {"success": False, "message": "PDF 中未提取到文本", "count": 0}

        chunks = semantic_chunk(text)
        doc_ids = pinecone_store.upsert_documents(
            chunks,
            namespace=pinecone_store.NS_RAG,
            metadata_base={"title": filename, "category": category, "source_type": "pdf"},
        )
        return {
            "success": True,
            "message": f"PDF '{filename}' 成功入库 {len(doc_ids)} 个知识片段",
            "count": len(doc_ids),
        }

    def retrieve(self, query: str, context: str = "") -> str:
        rewritten = llm_service.rewrite_query(query, context)
        results = pinecone_store.hybrid_search(
            rewritten, pinecone_store.NS_RAG, settings.rag_top_k
        )

        if not results:
            return ""

        parts = []
        for i, r in enumerate(results, 1):
            title = r.get("metadata", {}).get("title", "文档")
            category = r.get("metadata", {}).get("category", "")
            header = f"[{category}] {title}" if category else title
            parts.append(f"{i}. {header}\n{r['text']}")
        return "\n\n".join(parts)


rag_service = RAGService()
