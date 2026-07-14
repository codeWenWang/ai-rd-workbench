import hashlib

from app.domain.entities import Chunk, MemoryKind, MigrationSummary, ResourceStatus, ResourceType


class MigrationUseCase:
    def __init__(self, documents, memories, migrations, vector_index, settings) -> None:
        self.documents = documents
        self.memories = memories
        self.migrations = migrations
        self.vector_index = vector_index
        self.settings = settings

    async def run(self, *, dry_run: bool = True) -> MigrationSummary:
        summary = MigrationSummary()
        for namespace, resource_type in (
            (self.settings.pinecone_rag_namespace, ResourceType.KNOWLEDGE),
            (self.settings.pinecone_memory_namespace, ResourceType.MEMORY),
        ):
            async for vector_id in self.vector_index.list_ids(namespace):
                summary.scanned_vectors += 1
                if self.migrations.exists(namespace, vector_id):
                    summary.skipped_vectors += 1
                    continue
                fetched = await self.vector_index.fetch(namespace, [vector_id])
                if not fetched:
                    summary.failed_vectors += 1
                    summary.warnings.append(f"missing_vector:{namespace}:{vector_id}")
                    continue
                item = fetched[0]
                metadata = item.metadata
                content = str(metadata.get("text") or metadata.get("content") or "").strip()
                if not content:
                    summary.failed_vectors += 1
                    summary.warnings.append(f"missing_text:{namespace}:{vector_id}")
                    continue
                if dry_run:
                    summary.created_chunks += 1
                    continue
                if resource_type is ResourceType.KNOWLEDGE:
                    title = str(metadata.get("title") or "Migrated knowledge")
                    category = str(metadata.get("category") or "general")
                    document = self.documents.create(
                        title=title, category=category, source_type=str(metadata.get("source_type") or "migration"),
                        source_name=str(metadata.get("source_name") or title),
                        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    )
                    chunk = Chunk(id=str(metadata.get("chunk_id") or vector_id), document_id=document.id,
                                  content=content, namespace=namespace, vector_id=vector_id,
                                  chunk_index=int(metadata.get("chunk_index") or 0),
                                  page_number=_int_or_none(metadata.get("page_number")), title=title, category=category)
                    self.documents.save_chunks(document.id, [chunk])
                    self.documents.update_status(document.id, ResourceStatus.INDEXED)
                    target_id = chunk.id
                else:
                    memory = self.memories.create(title=str(metadata.get("title") or "Migrated memory"),
                                                  content=content, kind=MemoryKind.CONTEXT,
                                                  source_type="migration")
                    chunk = Chunk(id=str(metadata.get("chunk_id") or vector_id), memory_id=memory.id,
                                  content=content, namespace=namespace, vector_id=vector_id,
                                  page_number=_int_or_none(metadata.get("page_number")),
                                  title=memory.title, category=memory.kind.value)
                    self.memories.save_chunks(memory.id, [chunk])
                    target_id = chunk.id
                self.migrations.record(namespace=namespace, vector_id=vector_id,
                                       target_type=resource_type, target_id=target_id)
                summary.created_chunks += 1
        return summary


def _int_or_none(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
