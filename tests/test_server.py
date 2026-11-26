from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from ddgs.exceptions import DDGSException, TimeoutException
from mcp import Client

from tests.conftest import MockSearchBackend
from web_search_mcp.search import DdgsSearchBackend, SearchError
from web_search_mcp.server import mcp

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.conftest import FakeTime
    from web_search_mcp.models import SearchResult


@pytest.fixture
def patched_backend(mock_backend: MockSearchBackend) -> Iterator[MockSearchBackend]:
    with patch("web_search_mcp.server.backend", mock_backend):
        yield mock_backend


async def call_web_search(arguments: dict[str, Any]) -> Any:
    async with Client(mcp) as client:
        return await client.call_tool("web_search", arguments)


async def list_web_search_tool() -> Any:
    async with Client(mcp) as client:
        listed = await client.list_tools()
    matches = [tool for tool in listed.tools if tool.name == "web_search"]
    assert len(matches) == 1
    return matches[0]


def _failing_search(ddgs_error: Exception, fake_time: FakeTime) -> tuple[Any, Any]:
    ddgs_class = MagicMock()
    ddgs_class.return_value.text.side_effect = ddgs_error
    backend = DdgsSearchBackend(sleep=fake_time.sleep, clock=fake_time.clock)
    return ddgs_class, backend


async def test_top_level_query_is_accepted_and_reaches_backend(
    patched_backend: MockSearchBackend,
) -> None:
    result = await call_web_search({"query": "Python asyncio tutorial"})

    assert result.is_error is False
    assert [call["query"] for call in patched_backend.calls] == [
        "Python asyncio tutorial"
    ]


async def test_success_is_one_json_text_block_without_structured_content(
    patched_backend: MockSearchBackend, sample_results: list[SearchResult]
) -> None:
    result = await call_web_search({"query": "Python asyncio tutorial"})

    assert result.is_error is False
    assert len(result.content) == 1
    block = result.content[0]
    assert block.type == "text"
    assert json.loads(block.text) == {
        "results": [
            {"title": item.title, "url": item.url, "snippet": item.snippet}
            for item in sample_results
        ]
    }
    assert result.structured_content is None


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(SearchError("Search failed: network timeout"), id="search-error"),
        pytest.param(ConnectionError("network down"), id="other-exception"),
    ],
)
async def test_backend_failure_is_reported_as_tool_error(error: Exception) -> None:
    failing = MockSearchBackend(raises=error)
    with patch("web_search_mcp.server.backend", failing):
        result = await call_web_search({"query": "Python asyncio tutorial"})

    assert [call["query"] for call in failing.calls] == ["Python asyncio tutorial"]
    assert result.is_error is True


async def test_backend_search_error_message_reaches_the_client() -> None:
    failing = MockSearchBackend(raises=SearchError("Search failed: network timeout"))
    with patch("web_search_mcp.server.backend", failing):
        result = await call_web_search({"query": "Python asyncio tutorial"})

    assert result.is_error is True
    assert "Search failed: network timeout" in result.content[0].text


@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param(
            {"params": {"query": "Python asyncio tutorial"}}, id="arguments-in-params"
        ),
        pytest.param({"query": ""}, id="empty-query"),
        pytest.param({"query": "   "}, id="whitespace-only-query"),
        pytest.param({"query": "python", "max_results": 0}, id="max-results-below-1"),
        pytest.param({"query": "python", "max_results": 21}, id="max-results-above-20"),
        pytest.param({"query": "python", "max_results": 50}, id="max-results-50"),
        pytest.param(
            {"query": "python", "time_range": "decade"}, id="time-range-decade"
        ),
    ],
)
async def test_invalid_arguments_are_rejected_before_any_search(
    patched_backend: MockSearchBackend, arguments: dict[str, Any]
) -> None:
    result = await call_web_search(arguments)

    assert result.is_error is True
    assert patched_backend.calls == []


@pytest.mark.parametrize("max_results", [1, 20])
async def test_max_results_at_bounds_reaches_backend(
    patched_backend: MockSearchBackend, max_results: int
) -> None:
    result = await call_web_search({"query": "python", "max_results": max_results})

    assert result.is_error is False
    assert [call["max_results"] for call in patched_backend.calls] == [max_results]


@pytest.mark.parametrize("time_range", ["day", "week", "month", "year"])
async def test_time_range_value_reaches_backend(
    patched_backend: MockSearchBackend, time_range: str
) -> None:
    result = await call_web_search({"query": "python", "time_range": time_range})

    assert result.is_error is False
    assert [call["time_range"] for call in patched_backend.calls] == [time_range]


async def test_omitted_time_range_reaches_backend_as_none(
    patched_backend: MockSearchBackend,
) -> None:
    result = await call_web_search({"query": "python"})

    assert result.is_error is False
    assert [call["time_range"] for call in patched_backend.calls] == [None]


async def test_omitted_optional_arguments_reach_backend_as_defaults(
    patched_backend: MockSearchBackend,
) -> None:
    result = await call_web_search({"query": "python"})

    assert result.is_error is False
    assert patched_backend.calls == [
        {"query": "python", "max_results": 5, "region": None, "time_range": None}
    ]


async def test_region_reaches_backend(patched_backend: MockSearchBackend) -> None:
    result = await call_web_search({"query": "hello", "region": "us-en"})

    assert result.is_error is False
    assert [call["region"] for call in patched_backend.calls] == ["us-en"]


async def test_query_whitespace_is_stripped_before_search(
    patched_backend: MockSearchBackend,
) -> None:
    result = await call_web_search({"query": "  hello  "})

    assert result.is_error is False
    assert [call["query"] for call in patched_backend.calls] == ["hello"]


async def test_empty_results_are_returned_as_empty_results_list() -> None:
    with patch("web_search_mcp.server.backend", MockSearchBackend(results=[])):
        result = await call_web_search({"query": "test"})

    assert result.is_error is False
    assert json.loads(result.content[0].text) == {"results": []}


async def test_no_results_from_engines_is_a_tool_error_that_names_both_causes(
    fake_time: FakeTime,
) -> None:
    ddgs_class, backend = _failing_search(DDGSException("No results found."), fake_time)
    with (
        patch("web_search_mcp.search.DDGS", ddgs_class),
        patch("web_search_mcp.server.backend", backend),
    ):
        result = await call_web_search({"query": "python"})

    assert result.is_error is True
    text = result.content[0].text
    assert "refused" in text
    assert "not proof" in text
    assert "try again" in text.lower() or "change the query" in text.lower()


async def test_search_timeout_is_a_tool_error_that_says_timed_out(
    fake_time: FakeTime,
) -> None:
    ddgs_class, backend = _failing_search(
        TimeoutException("request timed out"), fake_time
    )
    with (
        patch("web_search_mcp.search.DDGS", ddgs_class),
        patch("web_search_mcp.server.backend", backend),
    ):
        result = await call_web_search({"query": "python"})

    assert result.is_error is True
    assert "timed out" in result.content[0].text


async def test_web_search_is_annotated_read_only_and_open_world() -> None:
    tool = await list_web_search_tool()

    assert tool.annotations.read_only_hint is True
    assert tool.annotations.open_world_hint is True
    assert tool.annotations.destructive_hint is None
    assert tool.annotations.idempotent_hint is None


async def test_web_search_description_is_at_most_1000_characters() -> None:
    tool = await list_web_search_tool()

    assert tool.description is not None
    assert len(tool.description) <= 1000


async def test_instructions_name_both_tools_and_mark_page_text_untrusted() -> None:
    async with Client(mcp) as client:
        instructions = client.instructions

    assert instructions is not None
    assert "web_search" in instructions
    assert "fetch_page" in instructions
    assert len(instructions) <= 2000
    assert "untrusted" in instructions.lower()
