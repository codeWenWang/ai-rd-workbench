import json

import jieba
import redis
from pinecone import Pinecone
from rank_bm25 import BM25Okapi

from app.config import settings
from app.services.document_processor import generate_id, semantic_chunk
from app.services.embedding_service import embedding_service


class PineconeStore:
    NS_RAG = "rag"
    NS_LTM = "ltm"

    def __init__(self):
        pc = Pinecone(api_key=settings.pinecone_api_key)
        if settings.pinecone_host:
            host = settings.pinecone_host
        else:
            index_info = pc.describe_index(settings.pinecone_index_name)
            host = index_info.host
        self.index = pc.Index(host=host)

        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
        )

    def _bm25_key(self, namespace: str) -> str:
        return f"bm25:{namespace}:corpus"

    def _bm25_ids_key(self, namespace: str) -> str:
        return f"bm25:{namespace}:ids"

    def _tokenize(self, text: str) -> list[str]:
        return list(jieba.cut_for_search(text))

    def _update_bm25_index(self, namespace: str, doc_id: str, text: str) -> None:
        corpus_key = self._bm25_key(namespace)
        ids_key = self._bm25_ids_key(namespace)

        existing_corpus = self.redis.get(corpus_key)
        existing_ids = self.redis.get(ids_key)

        corpus = json.loads(existing_corpus) if existing_corpus else []
        ids = json.loads(existing_ids) if existing_ids else []

        ids.append(doc_id)
        corpus.append(self._tokenize(text))

        self.redis.set(corpus_key, json.dumps(corpus, ensure_ascii=False))
        self.redis.set(ids_key, json.dumps(ids))

    def upsert_documents(
        self,
        texts: list[str],
        namespace: str,
        metadata_base: dict | None = None,
    ) -> list[str]:
        if not texts:
            return []

        embeddings = embedding_service.embed_batch(texts)
        doc_ids = []
        vectors = []

        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            doc_id = generate_id()
            doc_ids.append(doc_id)
            meta = {"text": text[:1000], **(metadata_base or {})}
            vectors.append({"id": doc_id, "values": embedding, "metadata": meta})
            self._update_bm25_index(namespace, doc_id, text)

        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            self.index.upsert(vectors=vectors[i : i + batch_size], namespace=namespace)

        return doc_ids

    def vector_search(
        self,
        query: str,
        namespace: str,
        top_k: int | None = None,
    ) -> list[dict]:
        top_k = top_k or settings.rag_top_k
        embedding = embedding_service.embed_text(query)
        result = self.index.query(
            vector=embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
        )
        return [
            {
                "id": match.id,
                "score": match.score,
                "text": match.metadata.get("text", ""),
                "metadata": match.metadata,
            }
            for match in result.matches
        ]

    def bm25_search(
        self,
        query: str,
        namespace: str,
        top_k: int | None = None,
    ) -> list[dict]:
        top_k = top_k or settings.rag_top_k

        corpus_key = self._bm25_key(namespace)
        ids_key = self._bm25_ids_key(namespace)

        existing_corpus = self.redis.get(corpus_key)
        existing_ids = self.redis.get(ids_key)

        if not existing_corpus or not existing_ids:
            return []

        corpus = json.loads(existing_corpus)
        ids = json.loads(existing_ids)

        if not corpus:
            return []

        bm25 = BM25Okapi(corpus)
        tokenized_query = self._tokenize(query)
        scores = bm25.get_scores(tokenized_query)

        scored = sorted(zip(ids, scores), key=lambda x: x[1], reverse=True)
        results = []
        for doc_id, score in scored[:top_k]:
            if score <= 0:
                continue
            fetch = self.index.fetch(ids=[doc_id], namespace=namespace)
            vectors = fetch.vectors or {}
            if doc_id in vectors:
                vec = vectors[doc_id]
                results.append(
                    {
                        "id": doc_id,
                        "score": float(score),
                        "text": (vec.metadata or {}).get("text", ""),
                        "metadata": vec.metadata or {},
                    }
                )
        return results

    def hybrid_search(
        self,
        query: str,
        namespace: str,
        top_k: int | None = None,
    ) -> list[dict]:
        top_k = top_k or settings.rag_top_k
        vector_results = self.vector_search(query, namespace, top_k * 2)
        bm25_results = self.bm25_search(query, namespace, top_k * 2)
        return _reciprocal_rank_fusion(vector_results, bm25_results, top_k)

    def delete_namespace(self, namespace: str) -> None:
        self.index.delete(delete_all=True, namespace=namespace)
        self.redis.delete(self._bm25_key(namespace))
        self.redis.delete(self._bm25_ids_key(namespace))


def _reciprocal_rank_fusion(
    list_a: list[dict],
    list_b: list[dict],
    top_k: int,
    k: int = 60,
) -> list[dict]:
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for rank, item in enumerate(list_a):
        doc_id = item["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = item

    for rank, item in enumerate(list_b):
        doc_id = item["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = item

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        {**doc_map[doc_id], "rrf_score": score}
        for doc_id, score in ranked
        if doc_id in doc_map
    ]


pinecone_store = PineconeStore()
