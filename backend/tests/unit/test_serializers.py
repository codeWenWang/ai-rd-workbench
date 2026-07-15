from datetime import datetime

from app.api.serializers import serialize
from app.domain.entities import Project


def test_serialize_treats_naive_database_datetimes_as_utc() -> None:
    project = Project(
        id="project-1",
        name="demo",
        root_path="C:/demo",
        last_scanned_at=datetime(2026, 7, 15, 9, 12),
    )

    payload = serialize(project)

    assert payload["last_scanned_at"] == "2026-07-15T09:12:00+00:00"
