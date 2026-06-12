from __future__ import annotations

import pytest

from web_search_mcp.models import SearchResult
from web_search_mcp.search import SearchError


class MockSearchBackend:
    def __init__(
        self,
        results: list[SearchResult] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._results = results or []
        self._raises = raises

    async def search(
        self, query: str, max_results: int, region: str | None
    ) -> list[SearchResult]:
        if self._raises is not None:
            raise self._raises
        return self._results


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


@pytest.fixture
def error_backend() -> MockSearchBackend:
    return MockSearchBackend(raises=SearchError("Search failed: network timeout"))
