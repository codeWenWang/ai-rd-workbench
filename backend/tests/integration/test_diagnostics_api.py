import asyncio
import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import AppContainer
from app.domain.entities import ComponentHealth
from app.main import create_app


class SlowUnavailableVectorIndex:
    async def health(self):
        await asyncio.sleep(1)
        return ComponentHealth("pinecone", False, "unavailable")


def test_diagnostics_returns_degraded_result_before_external_check_hangs(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'diagnostics.db').as_posix()}",
        diagnostics_timeout_seconds=0.05,
    )
    container = AppContainer(settings)
    container.vector_index = SlowUnavailableVectorIndex()
    client = TestClient(create_app(container=container))

    started = time.perf_counter()
    response = client.get("/api/diagnostics")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 0.5
    assert response.json()["status"] == "degraded"
    assert response.json()["components"]["pinecone"]["message"] == "timeout"
