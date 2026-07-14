import hashlib
from uuid import uuid4

from app.domain.entities import Chunk, IndexedChunk, ResourceStatus
from app.domain.errors import ResourceNotFound
from app.infrastructure.documents.loaders import load_pdf, load_text
from app.infrastructure.documents.splitters import split_pages


class DocumentUseCase:
    def __init__(self, repository, embeddings, vector_index, settings) -> None:
        self.repository = repository
        self.embeddings = embeddings
        self.vector_index = vector_index
        self.settings = settings

    async def ingest_text(self, text: str, *, title: str = "", category: str = "general"):
        pages = load_text(text, source_name=title or "text")
        return await self._ingest(pages, title=title or "Untitled", category=category,
                                  source_type="text", source_name=title or "text",
                                  raw_hash=hashlib.sha256(text.encode("utf-8")).hexdigest())

    async def ingest_pdf(self, data: bytes, *, filename: str, category: str = "general"):
        pages = load_pdf(data, source_name=filename, max_bytes=self.settings.upload_max_bytes,
                         max_pages=self.settings.pdf_max_pages)
        return await self._ingest(pages, title=filename, category=category, source_type="pdf",
                                  source_name=filename, raw_hash=hashlib.sha256(data).hexdigest())

    async def _ingest(self, pages, *, title, category, source_type, source_name, raw_hash):
        document = self.repository.create(title=title, category=category, source_type=source_type,
                                          source_name=source_name, content_hash=raw_hash)
        self.repository.update_status(document.id, ResourceStatus.INDEXING)
        try:
            parts = split_pages(pages, chunk_size=self.settings.rag_chunk_size,
                                chunk_overlap=self.settings.rag_chunk_overlap)
            vectors = await self.embeddings.embed_documents([part.content for part in parts])
            chunks = []
            indexed = []
            for index, (part, values) in enumerate(zip(parts, vectors, strict=True)):
                chunk_id = str(uuid4())
                vector_id = chunk_id
                chunk = Chunk(id=chunk_id, document_id=document.id, content=part.content,
                              namespace=self.settings.pinecone_rag_namespace, chunk_index=index,
                              page_number=part.metadata.get("page_number"), token_count=part.token_count,
                              vector_id=vector_id, title=title, category=category)
                chunks.append(chunk)
                indexed.append(IndexedChunk(vector_id, values, {
                    "chunk_id": chunk_id, "document_id": document.id, "text": part.content,
                    "title": title, "category": category, "page_number": chunk.page_number,
                }))
            self.repository.save_chunks(document.id, chunks)
            await self.vector_index.upsert(self.settings.pinecone_rag_namespace, indexed)
            return self.repository.update_status(document.id, ResourceStatus.INDEXED)
        except Exception as exc:
            self.repository.update_status(document.id, ResourceStatus.FAILED, error_message=str(exc))
            raise

    def list(self, **filters):
        return self.repository.list(**filters)

    def get(self, document_id: str):
        document = self.repository.get(document_id)
        if not document:
            raise ResourceNotFound("document not found")
        return document

    def update(self, document_id: str, *, title=None, category=None):
        return self.repository.update(document_id, title=title, category=category)

    async def reindex(self, document_id: str):
        document = self.get(document_id)
        chunks = self.repository.list_chunks(document_id)
        self.repository.update_status(document_id, ResourceStatus.INDEXING)
        try:
            values = await self.embeddings.embed_documents([chunk.content for chunk in chunks])
            indexed = [IndexedChunk(chunk.vector_id or chunk.id, vector, {
                "chunk_id": chunk.id, "document_id": document.id, "text": chunk.content,
                "title": document.title, "category": document.category, "page_number": chunk.page_number,
            }) for chunk, vector in zip(chunks, values, strict=True)]
            await self.vector_index.upsert(self.settings.pinecone_rag_namespace, indexed)
            return self.repository.update_status(document_id, ResourceStatus.INDEXED)
        except Exception as exc:
            self.repository.update_status(document_id, ResourceStatus.FAILED, error_message=str(exc))
            raise

    async def delete(self, document_id: str) -> None:
        document = self.get(document_id)
        self.repository.update_status(document.id, ResourceStatus.DELETING)
        chunks = self.repository.list_chunks(document_id)
        await self.vector_index.delete(self.settings.pinecone_rag_namespace,
                                       [chunk.vector_id for chunk in chunks if chunk.vector_id])
        self.repository.delete(document_id)
