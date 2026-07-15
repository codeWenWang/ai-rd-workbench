from app.domain.entities import (
    IndexedChunk,
    ProjectChunk,
    ResourceType,
    RetrievalResult,
    ScoredChunk,
)
from app.infrastructure.retrieval.hybrid import reciprocal_rank_fusion


def project_namespace(project_id: str) -> str:
    return f"project_{project_id}"


class ProjectIndexer:
    def __init__(self, analysis, embeddings, vector_index) -> None:
        self.analysis = analysis
        self.embeddings = embeddings
        self.vector_index = vector_index

    async def index(self, project_id: str) -> int:
        chunks = self.analysis.list_chunks(project_id)
        if not chunks:
            return 0
        vectors = await self.embeddings.embed_documents([item.content for item in chunks])
        indexed = [
            IndexedChunk(
                vector_id=item.vector_id or item.id,
                values=vector,
                metadata={
                    "chunk_id": item.id,
                    "project_id": project_id,
                    "resource_type": ResourceType.PROJECT.value,
                    "relative_path": item.relative_path,
                    "start_line": item.start_line,
                    "end_line": item.end_line,
                    "text": item.content,
                    "title": item.relative_path,
                },
            )
            for item, vector in zip(chunks, vectors, strict=True)
        ]
        await self.vector_index.upsert(project_namespace(project_id), indexed)
        return len(indexed)


class ProjectRetriever:
    def __init__(
        self,
        analysis,
        embeddings,
        vector_index,
        *,
        projects=None,
        limit: int = 6,
    ) -> None:
        self.analysis = analysis
        self.embeddings = embeddings
        self.vector_index = vector_index
        self.projects = projects
        self.limit = limit

    async def retrieve(self, project_id: str, query: str) -> RetrievalResult:
        lexical = [self._scored(item, 1.0 / index) for index, item in enumerate(
            self.analysis.search_chunks(project_id, query, self.limit), start=1
        )]
        overview = self._overview(project_id)
        warnings: list[str] = []
        semantic: list[ScoredChunk] = []
        try:
            vector = await self.embeddings.embed_query(query)
            semantic = await self.vector_index.query(
                project_namespace(project_id), vector, self.limit
            )
        except Exception:
            warnings.append("project_semantic_retrieval_unavailable")
        ranked = reciprocal_rank_fusion(lexical, semantic, limit=self.limit)
        return RetrievalResult(
            documents=self._merge_overview(overview, ranked),
            warnings=warnings,
        )

    def _overview(self, project_id: str) -> list[ScoredChunk]:
        documents: list[ScoredChunk] = []
        project = self.projects.get(project_id) if self.projects else None
        if project:
            source = project.source_uri or project.root_path
            tech_stack = "、".join(project.tech_stack) or "扫描结果中尚未识别"
            documents.append(ScoredChunk(
                chunk_id=f"project-overview:{project_id}",
                content=(
                    f"项目名称：{project.name}\n"
                    f"项目来源：{project.source_type}，{source}\n"
                    f"项目状态：{project.status}\n"
                    f"已识别技术栈：{tech_stack}"
                ),
                score=1.0,
                title="项目概览",
                resource_type=ResourceType.PROJECT,
                metadata={"project_id": project_id, "synthetic": True},
            ))
        list_overview = getattr(self.analysis, "list_overview_chunks", None)
        if list_overview:
            documents.extend(
                self._scored(item, 0.9 / index)
                for index, item in enumerate(list_overview(project_id, 4), start=1)
            )
        return documents

    def _merge_overview(
        self,
        overview: list[ScoredChunk],
        ranked: list[ScoredChunk],
    ) -> list[ScoredChunk]:
        merged: list[ScoredChunk] = []
        seen: set[str] = set()
        for item in overview + ranked:
            if item.chunk_id in seen:
                continue
            seen.add(item.chunk_id)
            merged.append(item)
            if len(merged) >= self.limit:
                break
        return merged

    @staticmethod
    def _scored(item: ProjectChunk, score: float) -> ScoredChunk:
        return ScoredChunk(
            chunk_id=item.id,
            content=item.content,
            score=score,
            title=item.relative_path,
            resource_type=ResourceType.PROJECT,
            vector_id=item.vector_id,
            metadata={
                "project_id": item.project_id,
                "relative_path": item.relative_path,
                "start_line": item.start_line,
                "end_line": item.end_line,
            },
        )
