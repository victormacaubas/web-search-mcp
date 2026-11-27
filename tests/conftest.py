from __future__ import annotations

from typing import Any

import pytest

from web_search_mcp.models import SearchResult, TimeRange


class MockSearchBackend:
    def __init__(
        self,
        results: list[SearchResult] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._results = results or []
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        query: str,
        max_results: int,
        region: str | None,
        time_range: TimeRange | None,
    ) -> list[SearchResult]:
        self.calls.append(
            {
                "query": query,
                "max_results": max_results,
                "region": region,
                "time_range": time_range,
            }
        )
        if self._raises is not None:
            raise self._raises
        return self._results


class FakeTime:
    """Virtual clock and sleep, so that no test waits on the wall clock."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def sample_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Python asyncio docs",
            url="https://docs.python.org/3/library/asyncio.html",
            snippet="asyncio is a library to write concurrent code using async/await.",
        ),
        SearchResult(
            title="Real Python asyncio guide",
            url="https://realpython.com/async-io-python/",
            snippet="A complete walkthrough of Python's asyncio library.",
        ),
        SearchResult(
            title="asyncio tutorial",
            url="https://example.com/asyncio-tutorial",
            snippet="Learn asyncio from scratch.",
        ),
    ]


@pytest.fixture
def mock_backend(sample_results: list[SearchResult]) -> MockSearchBackend:
    return MockSearchBackend(results=sample_results)
