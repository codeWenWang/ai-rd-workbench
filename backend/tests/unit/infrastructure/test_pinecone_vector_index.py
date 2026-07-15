import threading

from app.config import Settings
from app.infrastructure.vectorstores.pinecone import PineconeVectorIndex, _sanitize_metadata


def test_sanitize_metadata_removes_null_values() -> None:
    metadata = {
        "text": "Python 3.11",
        "page_number": None,
        "priority": 1,
        "confirmed": True,
        "tags": ["python", "preference"],
    }

    assert _sanitize_metadata(metadata) == {
        "text": "Python 3.11",
        "priority": 1,
        "confirmed": True,
        "tags": ["python", "preference"],
    }


async def test_health_initializes_pinecone_index_outside_the_event_loop_thread() -> None:
    event_loop_thread = threading.get_ident()
    initialization_threads = []

    class FakeIndex:
        def describe_index_stats(self):
            return {"dimension": 1024}

    vector_index = PineconeVectorIndex(Settings(pinecone_api_key="test-key"))

    def get_index():
        initialization_threads.append(threading.get_ident())
        return FakeIndex()

    vector_index._get_index = get_index

    health = await vector_index.health()

    assert health.ok is True
    assert initialization_threads
    assert initialization_threads[0] != event_loop_thread
