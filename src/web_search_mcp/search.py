"""Search backend protocol and the ddgs backend with its retry and rate limit."""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

from ddgs import DDGS
from ddgs.exceptions import DDGSException, TimeoutException

from web_search_mcp.models import SearchResult, TimeRange

logger = logging.getLogger(__name__)

DDGS_TIMEOUT_SECONDS = 10
MIN_INTERVAL_SECONDS = 1.0
RETRY_DELAY_MIN_SECONDS = 1.0
RETRY_DELAY_MAX_SECONDS = 2.0
MAX_ATTEMPTS = 2

_TIMELIMITS: dict[TimeRange, str] = {
    "day": "d",
    "week": "w",
    "month": "m",
    "year": "y",
}

_TIMEOUT_MESSAGE = (
    "Search timed out: the search engines did not answer in time. "
    "Try again, or change the query."
)
_REFUSED_MESSAGE = (
    "Search returned no results: the search engines found nothing, or they "
    "refused the request. An empty answer is not proof that no pages exist. "
    "Try again after a short wait, or change the query."
)


class SearchError(Exception):
    pass


class SearchBackend(Protocol):
    async def search(
        self,
        query: str,
        max_results: int,
        region: str | None,
        time_range: TimeRange | None,
    ) -> list[SearchResult]: ...


def _default_retry_delay() -> float:
    return random.uniform(RETRY_DELAY_MIN_SECONDS, RETRY_DELAY_MAX_SECONDS)


class DdgsSearchBackend:
    """Search backend for ddgs, which scrapes search engines.

    Searches run one at a time with a minimum interval between starts, and a
    failed search is tried once more. These rules protect a scraped service
    from bursts and do not belong to the `SearchBackend` protocol.
    """

    def __init__(
        self,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        min_interval: float = MIN_INTERVAL_SECONDS,
        retry_delay: Callable[[], float] = _default_retry_delay,
    ) -> None:
        self._sleep = sleep
        self._clock = clock
        self._min_interval = min_interval
        self._retry_delay = retry_delay
        self._lock = asyncio.Lock()
        self._last_start: float | None = None

    async def search(
        self,
        query: str,
        max_results: int,
        region: str | None,
        time_range: TimeRange | None,
    ) -> list[SearchResult]:
        timelimit = _TIMELIMITS[time_range] if time_range is not None else None
        async with self._lock:
            failure: DDGSException | None = None
            for attempt in range(MAX_ATTEMPTS):
                if attempt > 0:
                    logger.warning("Search attempt %d failed: %s", attempt, failure)
                    await self._sleep(self._retry_delay())
                await self._wait_for_interval()
                try:
                    return await self._search_once(
                        query, max_results, region or "wt-wt", timelimit
                    )
                except DDGSException as exc:
                    failure = exc
        if isinstance(failure, TimeoutException):
            raise SearchError(_TIMEOUT_MESSAGE) from failure
        raise SearchError(_REFUSED_MESSAGE) from failure

    async def _wait_for_interval(self) -> None:
        if self._last_start is not None:
            remaining = self._min_interval - (self._clock() - self._last_start)
            if remaining > 0:
                await self._sleep(remaining)
        self._last_start = self._clock()

    async def _search_once(
        self, query: str, max_results: int, region: str, timelimit: str | None
    ) -> list[SearchResult]:
        raw = await asyncio.to_thread(
            DDGS(timeout=DDGS_TIMEOUT_SECONDS).text,
            query,
            max_results=max_results,
            region=region,
            timelimit=timelimit,
        )
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
            )
            for r in raw
        ]
