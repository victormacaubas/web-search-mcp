from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from web_search_mcp.models import SearchResult
from web_search_mcp.search import DdgsSearchBackend, SearchError

_FAKE_DDGS_RESULTS = [
    {"title": "Result One", "href": "https://example.com/1", "body": "Snippet one."},
    {"title": "Result Two", "href": "https://example.com/2", "body": "Snippet two."},
]


async def test_search_maps_results_to_search_result_instances() -> None:
    backend = DdgsSearchBackend()
    ddgs_instance = MagicMock()
    ddgs_instance.text.return_value = _FAKE_DDGS_RESULTS

    with patch("web_search_mcp.search.DDGS", return_value=ddgs_instance):
        results = await backend.search("python", max_results=5, region=None)

    assert len(results) == 2
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].title == "Result One"
    assert results[0].url == "https://example.com/1"
    assert results[0].snippet == "Snippet one."
    assert results[1].title == "Result Two"
    assert results[1].url == "https://example.com/2"
    assert results[1].snippet == "Snippet two."


async def test_search_passes_region_none_as_wt_wt() -> None:
    backend = DdgsSearchBackend()
    ddgs_instance = MagicMock()
    ddgs_instance.text.return_value = []

    with patch("web_search_mcp.search.DDGS", return_value=ddgs_instance):
        await backend.search("python", max_results=5, region=None)

    ddgs_instance.text.assert_called_once_with("python", max_results=5, region="wt-wt")


async def test_search_passes_explicit_region() -> None:
    backend = DdgsSearchBackend()
    ddgs_instance = MagicMock()
    ddgs_instance.text.return_value = []

    with patch("web_search_mcp.search.DDGS", return_value=ddgs_instance):
        await backend.search("python", max_results=3, region="us-en")

    ddgs_instance.text.assert_called_once_with("python", max_results=3, region="us-en")


async def test_search_raises_search_error_when_ddgs_raises() -> None:
    backend = DdgsSearchBackend()
    ddgs_instance = MagicMock()
    ddgs_instance.text.side_effect = RuntimeError("connection refused")

    with (
        patch("web_search_mcp.search.DDGS", return_value=ddgs_instance),
        pytest.raises(SearchError) as exc_info,
    ):
        await backend.search("python", max_results=5, region=None)

    assert "Search failed" in str(exc_info.value)
    assert "connection refused" in str(exc_info.value)
