from app.domain.entities import Project, ProjectChunk, ResourceType, ScoredChunk
from app.infrastructure.retrieval.project import ProjectIndexer, ProjectRetriever


class FakeAnalysis:
    def list_chunks(self, project_id):
        return [ProjectChunk(
            id="chunk-1", project_id=project_id, project_file_id="file-1",
            relative_path="app/main.py", content="FastAPI health route",
            start_line=1, end_line=8, vector_id="chunk-1",
        )]

    def search_chunks(self, project_id, query, limit=6):
        return self.list_chunks(project_id)

    def list_overview_chunks(self, project_id, limit=4):
        return [ProjectChunk(
            id="readme-chunk", project_id=project_id, project_file_id="readme-file",
            relative_path="README.md", content="这是一个音乐网站项目。",
            start_line=1, end_line=4, vector_id="readme-chunk",
        )]


class FakeProjects:
    def get(self, project_id):
        return Project(
            id=project_id,
            name="Music Website",
            root_path="C:/cache/music-website",
            source_type="gitee",
            source_uri="https://gitee.com/example/music-website.git",
            status="ready",
            tech_stack=["html", "javascript", "css"],
        )


class FakeEmbeddings:
    async def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]

    async def embed_query(self, text):
        return [0.1, 0.2]


class FakeVectorIndex:
    def __init__(self):
        self.upserts = []

    async def upsert(self, namespace, chunks):
        self.upserts.append((namespace, chunks))

    async def query(self, namespace, vector, limit):
        return [ScoredChunk(
            chunk_id="chunk-1", content="FastAPI health route", score=0.9,
            resource_type=ResourceType.PROJECT, vector_id="chunk-1",
            metadata={"relative_path": "app/main.py", "start_line": 1, "end_line": 8},
        )]


class UnavailableEmbeddings:
    async def embed_query(self, text):
        raise RuntimeError("embedding service unavailable")


async def test_project_indexer_uses_isolated_namespace_and_source_metadata() -> None:
    vector_index = FakeVectorIndex()
    indexer = ProjectIndexer(FakeAnalysis(), FakeEmbeddings(), vector_index)

    count = await indexer.index("project-1")

    namespace, chunks = vector_index.upserts[0]
    assert count == 1
    assert namespace == "project_project-1"
    assert chunks[0].metadata["relative_path"] == "app/main.py"
    assert chunks[0].metadata["resource_type"] == "project"


async def test_project_retriever_fuses_local_and_semantic_results() -> None:
    retriever = ProjectRetriever(
        FakeAnalysis(), FakeEmbeddings(), FakeVectorIndex(), projects=FakeProjects()
    )

    result = await retriever.retrieve("project-1", "health")

    assert result.documents[0].resource_type is ResourceType.PROJECT
    assert "Music Website" in result.documents[0].content
    assert result.warnings == []


async def test_project_retriever_keeps_project_overview_when_semantic_search_is_unavailable() -> None:
    retriever = ProjectRetriever(
        FakeAnalysis(), UnavailableEmbeddings(), FakeVectorIndex(), projects=FakeProjects()
    )

    result = await retriever.retrieve("project-1", "简单介绍一下这个项目的主要技术栈")

    assert "Music Website" in result.documents[0].content
    assert "html、javascript、css" in result.documents[0].content
    assert any(item.title == "README.md" for item in result.documents)
    assert result.warnings == ["project_semantic_retrieval_unavailable"]
