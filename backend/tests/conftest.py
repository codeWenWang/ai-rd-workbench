import os

import pytest


@pytest.fixture
def live_network_enabled() -> bool:
    return os.getenv("RUN_LIVE_TESTS") == "1"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.getenv("RUN_LIVE_TESTS") == "1":
        return

    skip_live = pytest.mark.skip(
        reason="live test disabled; set RUN_LIVE_TESTS=1 to enable it"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
