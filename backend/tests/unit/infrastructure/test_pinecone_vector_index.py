from app.infrastructure.vectorstores.pinecone import _sanitize_metadata


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
