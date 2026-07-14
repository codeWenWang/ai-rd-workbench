from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.domain.entities import ResourceType, ScoredChunk


class SqliteFtsSearch:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def search(self, query: str, resource_type: ResourceType, limit: int) -> list[ScoredChunk]:
        cleaned = query.strip().replace('"', ' ')
        if not cleaned:
            return []
        with self.sessions() as session:
            try:
                rows = session.execute(text(
                    "SELECT f.chunk_id, f.content, f.title, f.category, bm25(chunks_fts) score, "
                    "c.document_id, c.memory_id, c.page_number, c.vector_id "
                    "FROM chunks_fts f JOIN chunks c ON c.id=f.chunk_id "
                    "WHERE chunks_fts MATCH :query AND f.resource_type=:resource_type "
                    "ORDER BY score LIMIT :limit"
                ), {"query": cleaned, "resource_type": resource_type.value, "limit": limit}).mappings().all()
            except SQLAlchemyError:
                session.rollback()
                rows = []
            if not rows:
                rows = session.execute(text(
                    "SELECT c.id chunk_id, c.content, c.title, c.category, 0.0 score, c.document_id, "
                    "c.memory_id, c.page_number, c.vector_id FROM chunks c WHERE c.content LIKE :query "
                    "AND ((:resource_type='knowledge' AND c.document_id IS NOT NULL) OR "
                    "(:resource_type='memory' AND c.memory_id IS NOT NULL)) LIMIT :limit"
                ), {"query": f"%{cleaned}%", "resource_type": resource_type.value, "limit": limit}).mappings().all()
        return [ScoredChunk(chunk_id=row["chunk_id"], content=row["content"], score=float(-row["score"]),
                            title=row["title"], category=row["category"], page_number=row["page_number"],
                            resource_type=resource_type, document_id=row["document_id"], memory_id=row["memory_id"],
                            vector_id=row["vector_id"]) for row in rows]
