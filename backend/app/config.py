from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI R&D Enablement Platform"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'app.db').as_posix()}"
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    embedding_model: str = "text-embedding-v4"
    embedding_dimension: int = 1024
    pinecone_api_key: str = ""
    pinecone_index_name: str = "1"
    pinecone_host: str = ""
    pinecone_rag_namespace: str = "rag"
    pinecone_memory_namespace: str = "ltm"
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_chunk_size: int = Field(default=500, ge=100, le=4000)
    rag_chunk_overlap: int = Field(default=50, ge=0, le=1000)
    upload_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    pdf_max_pages: int = Field(default=300, ge=1)
    git_cache_dir: str = str(BACKEND_DIR / "data" / "git-projects")
    git_clone_timeout_seconds: int = Field(default=180, ge=10, le=1800)
    git_update_timeout_seconds: int = Field(default=90, ge=5, le=600)


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Compatibility for legacy modules. New code receives settings lazily.
settings = get_settings()
