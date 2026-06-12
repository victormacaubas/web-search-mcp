from __future__ import annotations

import json
from unittest.mock import patch

from tests.conftest import MockSearchBackend
from web_search_mcp.models import SearchResult, WebSearchInput
from web_search_mcp.search import SearchError
from web_search_mcp.server import web_search

_KNOWN_RESULTS = [
    SearchResult(
        title="Test Title",
        url="https://example.com",
        snippet="A test snippet.",
    )
]


async def test_web_search_returns_json_with_results_shape() -> None:
    mock = MockSearchBackend(results=_KNOWN_RESULTS)
    with patch("web_search_mcp.server.backend", mock):
        raw = await web_search(WebSearchInput(query="test"))

    payload = json.loads(raw)
    assert "results" in payload
    assert len(payload["results"]) == 1

    result = payload["results"][0]
    assert isinstance(result["title"], str)
    assert isinstance(result["url"], str)
    assert isinstance(result["snippet"], str)
    assert result["title"] == "Test Title"
    assert result["url"] == "https://example.com"
    assert result["snippet"] == "A test snippet."


async def test_web_search_returns_error_string_on_search_error() -> None:
    mock = MockSearchBackend(raises=SearchError("Search failed: timeout"))
    with patch("web_search_mcp.server.backend", mock):
        result = await web_search(WebSearchInput(query="test"))

    assert result.startswith("Error:")
    assert "Search failed: timeout" in result


async def test_web_search_returns_empty_results_list_when_no_results() -> None:
    mock = MockSearchBackend(results=[])
    with patch("web_search_mcp.server.backend", mock):
        raw = await web_search(WebSearchInput(query="test"))

    payload = json.loads(raw)
    assert payload == {"results": []}


async def test_web_search_passes_all_params_to_backend() -> None:
    received: list[tuple[str, int, str | None]] = []

    class CapturingBackend:
        async def search(
            self, query: str, max_results: int, region: str | None
        ) -> list[SearchResult]:
            received.append((query, max_results, region))
            return []

    with patch("web_search_mcp.server.backend", CapturingBackend()):
        await web_search(WebSearchInput(query="hello", max_results=10, region="us-en"))

    assert received == [("hello", 10, "us-en")]
