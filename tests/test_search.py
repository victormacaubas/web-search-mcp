from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from ddgs.exceptions import DDGSException, TimeoutException

from web_search_mcp.models import SearchResult
from web_search_mcp.search import DdgsSearchBackend, SearchError

if TYPE_CHECKING:
    from tests.conftest import FakeTime

_FAKE_DDGS_RESULTS = [
    {"title": "Result One", "href": "https://example.com/1", "body": "Snippet one."},
    {"title": "Result Two", "href": "https://example.com/2", "body": "Snippet two."},
]


def _backend(fake_time: FakeTime) -> DdgsSearchBackend:
    return DdgsSearchBackend(sleep=fake_time.sleep, clock=fake_time.clock)


def _ddgs_class(
    text_result: object = None, text_error: Exception | None = None
) -> MagicMock:
    ddgs_class = MagicMock()
    if text_error is not None:
        ddgs_class.return_value.text.side_effect = text_error
    else:
        ddgs_class.return_value.text.return_value = text_result
    return ddgs_class


async def test_search_maps_results_to_search_result_instances(
    fake_time: FakeTime,
) -> None:
    ddgs_class = _ddgs_class(text_result=_FAKE_DDGS_RESULTS)

    with patch("web_search_mcp.search.DDGS", ddgs_class):
        results = await _backend(fake_time).search(
            "python", max_results=5, region=None, time_range=None
        )

    assert len(results) == 2
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].title == "Result One"
    assert results[0].url == "https://example.com/1"
    assert results[0].snippet == "Snippet one."
    assert results[1].title == "Result Two"
    assert results[1].url == "https://example.com/2"
    assert results[1].snippet == "Snippet two."


async def test_ddgs_client_is_constructed_with_ten_second_timeout(
    fake_time: FakeTime,
) -> None:
    ddgs_class = _ddgs_class(text_result=[])

    with patch("web_search_mcp.search.DDGS", ddgs_class):
        await _backend(fake_time).search(
            "python", max_results=5, region=None, time_range=None
        )

    assert ddgs_class.call_args.kwargs.get("timeout") == 10


@pytest.mark.parametrize(
    ("region", "expected"),
    [
        pytest.param(None, "wt-wt", id="no-region-uses-worldwide"),
        pytest.param("us-en", "us-en", id="explicit-region"),
    ],
)
async def test_region_is_passed_to_ddgs(
    fake_time: FakeTime, region: str | None, expected: str
) -> None:
    ddgs_class = _ddgs_class(text_result=[])

    with patch("web_search_mcp.search.DDGS", ddgs_class):
        await _backend(fake_time).search(
            "python", max_results=5, region=region, time_range=None
        )

    assert ddgs_class.return_value.text.call_args.kwargs.get("region") == expected


@pytest.mark.parametrize(
    ("time_range", "expected_timelimit"),
    [
        pytest.param("day", "d", id="day"),
        pytest.param("week", "w", id="week"),
        pytest.param("month", "m", id="month"),
        pytest.param("year", "y", id="year"),
        pytest.param(None, None, id="no-time-range-has-no-date-limit"),
    ],
)
async def test_time_range_is_mapped_to_ddgs_timelimit(
    fake_time: FakeTime, time_range: str | None, expected_timelimit: str | None
) -> None:
    ddgs_class = _ddgs_class(text_result=[])

    with patch("web_search_mcp.search.DDGS", ddgs_class):
        await _backend(fake_time).search(
            "python", max_results=5, region=None, time_range=time_range
        )

    text_kwargs = ddgs_class.return_value.text.call_args.kwargs
    assert text_kwargs.get("timelimit") == expected_timelimit


async def test_timeout_is_raised_as_search_error_that_says_timed_out(
    fake_time: FakeTime,
) -> None:
    ddgs_class = _ddgs_class(text_error=TimeoutException("request timed out"))

    with (
        patch("web_search_mcp.search.DDGS", ddgs_class),
        pytest.raises(SearchError) as exc_info,
    ):
        await _backend(fake_time).search(
            "python", max_results=5, region=None, time_range=None
        )

    assert "timed out" in str(exc_info.value)


async def test_no_results_is_raised_as_search_error_with_both_causes(
    fake_time: FakeTime,
) -> None:
    ddgs_class = _ddgs_class(text_error=DDGSException("No results found."))

    with (
        patch("web_search_mcp.search.DDGS", ddgs_class),
        pytest.raises(SearchError) as exc_info,
    ):
        await _backend(fake_time).search(
            "python", max_results=5, region=None, time_range=None
        )

    message = str(exc_info.value)
    assert "refused" in message
    assert "not proof" in message
    assert "try again" in message.lower() or "change the query" in message.lower()


async def test_second_attempt_returns_results_when_first_attempt_fails(
    fake_time: FakeTime,
) -> None:
    ddgs_class = _ddgs_class()
    ddgs_class.return_value.text.side_effect = [
        DDGSException("temporary failure"),
        _FAKE_DDGS_RESULTS,
    ]

    with patch("web_search_mcp.search.DDGS", ddgs_class):
        results = await _backend(fake_time).search(
            "python", max_results=5, region=None, time_range=None
        )

    assert [r.title for r in results] == ["Result One", "Result Two"]
    assert ddgs_class.return_value.text.call_count == 2
    assert fake_time.sleeps
    assert all(1 <= delay <= 2 for delay in fake_time.sleeps)


async def test_two_failed_attempts_raise_one_search_error_after_exactly_two_attempts(
    fake_time: FakeTime,
) -> None:
    ddgs_class = _ddgs_class(text_error=DDGSException("temporary failure"))

    with (
        patch("web_search_mcp.search.DDGS", ddgs_class),
        pytest.raises(SearchError),
    ):
        await _backend(fake_time).search(
            "python", max_results=5, region=None, time_range=None
        )

    assert ddgs_class.return_value.text.call_count == 2
    assert fake_time.sleeps
    assert all(1 <= delay <= 2 for delay in fake_time.sleeps)


async def test_ddgs_failure_is_raised_as_search_error(fake_time: FakeTime) -> None:
    ddgs_class = _ddgs_class(text_error=DDGSException("connection refused"))

    with (
        patch("web_search_mcp.search.DDGS", ddgs_class),
        pytest.raises(SearchError),
    ):
        await _backend(fake_time).search(
            "python", max_results=5, region=None, time_range=None
        )


async def test_concurrent_searches_do_not_overlap_in_the_backend(
    fake_time: FakeTime,
) -> None:
    guard = threading.Lock()
    in_flight = 0
    peak = 0

    def slow_text(query: str, **kwargs: object) -> list[dict[str, str]]:
        nonlocal in_flight, peak
        with guard:
            in_flight += 1
            peak = max(peak, in_flight)
        # Hold the call open so that an overlapping call would be seen.
        time.sleep(0.05)
        with guard:
            in_flight -= 1
        return _FAKE_DDGS_RESULTS

    ddgs_class = _ddgs_class()
    ddgs_class.return_value.text.side_effect = slow_text

    with patch("web_search_mcp.search.DDGS", ddgs_class):
        backend = _backend(fake_time)
        results = await asyncio.gather(
            *(
                backend.search("python", max_results=5, region=None, time_range=None)
                for _ in range(3)
            )
        )

    assert peak == 1
    assert [len(batch) for batch in results] == [2, 2, 2]
