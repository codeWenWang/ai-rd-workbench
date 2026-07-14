import os
from typing import Any

import pytest

import conftest


class FakeItem:
    def __init__(self, *, live: bool) -> None:
        self.keywords = {"live": True} if live else {}
        self.markers: list[Any] = []

    def add_marker(self, marker: Any) -> None:
        self.markers.append(marker)


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") == "1",
    reason="default-mode assertion is not applicable during live test runs",
)
def test_tests_block_live_network_by_default(live_network_enabled: bool) -> None:
    assert live_network_enabled is False


def test_live_marker_is_skipped_when_environment_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RUN_LIVE_TESTS", raising=False)
    item = FakeItem(live=True)

    conftest.pytest_collection_modifyitems(items=[item])

    assert len(item.markers) == 1
    assert item.markers[0].mark.name == "skip"
    assert "RUN_LIVE_TESTS=1" in item.markers[0].mark.kwargs["reason"]


def test_live_marker_is_enabled_when_environment_is_exactly_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUN_LIVE_TESTS", "1")
    item = FakeItem(live=True)

    conftest.pytest_collection_modifyitems(items=[item])

    assert item.markers == []


def test_unmarked_tests_are_not_skipped_when_live_tests_are_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RUN_LIVE_TESTS", raising=False)
    item = FakeItem(live=False)

    conftest.pytest_collection_modifyitems(items=[item])

    assert item.markers == []


def test_pytest_requires_registered_markers(pytestconfig: pytest.Config) -> None:
    assert "--strict-markers" in pytestconfig.getini("addopts")
