from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import chat_v2, diagnostics, documents_v2, memories_v2
from app.api.errors import domain_error_handler, unexpected_error_handler
from app.config import Settings
from app.dependencies import AppContainer
from app.domain.errors import DomainError


def create_app(*, settings: Settings | None = None, container: AppContainer | None = None) -> FastAPI:
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    application = FastAPI(
        title="研发知识工作台 API",
        description="本地单人知识库、长期记忆与可控 RAG 问答接口",
        version="2.0.0",
        docs_url=None,
        redoc_url=None,
    )
    application.state.container = container or AppContainer(settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_exception_handler(DomainError, domain_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
    application.include_router(chat_v2.router)
    application.include_router(documents_v2.router)
    application.include_router(memories_v2.router)
    application.include_router(diagnostics.router)

    @application.get("/docs", include_in_schema=False)
    def api_docs():
        return FileResponse(frontend_dir / "docs.html", media_type="text/html")

    if frontend_dir.exists():
        application.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    return application


app = create_app()
