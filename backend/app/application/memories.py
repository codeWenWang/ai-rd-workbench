from uuid import uuid4

from app.domain.entities import CandidateStatus, Chunk, IndexedChunk, MemoryKind
from app.domain.errors import ResourceNotFound, ValidationError
from app.infrastructure.documents.loaders import load_pdf, load_text
from app.infrastructure.documents.splitters import split_pages


class MemoryUseCase:
    def __init__(self, repository, embeddings, vector_index, settings) -> None:
        self.repository = repository
        self.embeddings = embeddings
        self.vector_index = vector_index
        self.settings = settings

    async def create_text(self, text: str, *, title="", kind=MemoryKind.CONTEXT, source_conversation_id=None):
        pages = load_text(text, source_name=title or "memory")
        for existing in self.repository.list_confirmed(include_archived=False, offset=0, limit=1000):
            if existing.content.strip().casefold() == text.strip().casefold():
                chunks = self.repository.list_chunks(existing.id)
                vector_ids = [chunk.vector_id for chunk in chunks if chunk.vector_id]
                remote = await self.vector_index.fetch(
                    self.settings.pinecone_memory_namespace,
                    vector_ids,
                )
                if not vector_ids or {item.vector_id for item in remote} != set(vector_ids):
                    return await self.update(existing.id)
                return existing
        return await self._create(pages, title=title or "个人记忆", content=text, kind=kind,
                                  source_type="text", source_conversation_id=source_conversation_id)

    async def create_pdf(self, data: bytes, *, filename: str, kind=MemoryKind.CONTEXT, source_conversation_id=None):
        pages = load_pdf(data, source_name=filename, max_bytes=self.settings.upload_max_bytes,
                         max_pages=self.settings.pdf_max_pages)
        return await self._create(pages, title=filename, content="\n\n".join(p.content for p in pages),
                                  kind=kind, source_type="pdf", source_conversation_id=source_conversation_id)

    async def _create(self, pages, *, title, content, kind, source_type, source_conversation_id):
        memory = self.repository.create(title=title, content=content, kind=kind, source_type=source_type,
                                        source_conversation_id=source_conversation_id)
        await self._index(memory, pages)
        return memory

    async def _index(self, memory, pages=None):
        pages = pages or load_text(memory.content, source_name=memory.title)
        parts = split_pages(pages, chunk_size=self.settings.rag_chunk_size,
                            chunk_overlap=self.settings.rag_chunk_overlap)
        values = await self.embeddings.embed_documents([part.content for part in parts])
        chunks, indexed = [], []
        for index, (part, vector) in enumerate(zip(parts, values, strict=True)):
            chunk_id = str(uuid4())
            chunk = Chunk(id=chunk_id, memory_id=memory.id, content=part.content,
                          namespace=self.settings.pinecone_memory_namespace, chunk_index=index,
                          page_number=part.metadata.get("page_number"), token_count=part.token_count,
                          vector_id=chunk_id, title=memory.title, category=memory.kind.value)
            chunks.append(chunk)
            indexed.append(IndexedChunk(chunk_id, vector, {"chunk_id": chunk_id, "memory_id": memory.id,
                "text": part.content, "title": memory.title, "category": memory.kind.value,
                "page_number": chunk.page_number}))
        self.repository.save_chunks(memory.id, chunks)
        await self.vector_index.upsert(self.settings.pinecone_memory_namespace, indexed)

    def list(self, **filters):
        return self.repository.list_confirmed(**filters)

    async def update(self, memory_id: str, **changes):
        old_chunks = self.repository.list_chunks(memory_id)
        memory = self.repository.update(memory_id, **changes)
        await self.vector_index.delete(self.settings.pinecone_memory_namespace,
                                       [chunk.vector_id for chunk in old_chunks if chunk.vector_id])
        await self._index(memory)
        return memory

    async def delete(self, memory_id: str) -> None:
        chunks = self.repository.list_chunks(memory_id)
        await self.vector_index.delete(self.settings.pinecone_memory_namespace,
                                       [chunk.vector_id for chunk in chunks if chunk.vector_id])
        self.repository.delete(memory_id)

    def create_candidate(self, *, title, content, kind=MemoryKind.CONTEXT, conversation_id=None, message_id=None):
        return self.repository.create_candidate(title=title, content=content, kind=kind,
                                                conversation_id=conversation_id, message_id=message_id)

    def list_candidates(self, **filters):
        return self.repository.list_candidates(**filters)

    def update_candidate(self, candidate_id: str, **changes):
        return self.repository.update_candidate(candidate_id, **changes)

    async def confirm_candidate(self, candidate_id: str):
        candidate = self.repository.get_candidate(candidate_id)
        if not candidate:
            raise ResourceNotFound("memory candidate not found")
        if candidate.status is not CandidateStatus.PENDING:
            raise ValidationError("memory candidate has already been reviewed")
        memory = await self.create_text(candidate.proposed_content, title=candidate.proposed_title,
                                        kind=candidate.kind, source_conversation_id=candidate.conversation_id)
        self.repository.update_candidate_status(candidate_id, CandidateStatus.CONFIRMED)
        return memory

    def reject_candidate(self, candidate_id: str):
        return self.repository.update_candidate_status(candidate_id, CandidateStatus.REJECTED)
