import asyncio
from typing import Protocol

from ddgs import DDGS
from ddgs.exceptions import DDGSException

from web_search_mcp.models import SearchResult


class SearchError(Exception):
    pass


class SearchBackend(Protocol):
    async def search(
        self, query: str, max_results: int, region: str | None
    ) -> list[SearchResult]: ...


class DdgsSearchBackend:
    async def search(
        self, query: str, max_results: int, region: str | None
    ) -> list[SearchResult]:
        try:
            raw = await asyncio.to_thread(
                DDGS().text,
                query,
                max_results=max_results,
                region=region or "wt-wt",
            )
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                )
                for r in raw
            ]
        except DDGSException as exc:
            raise SearchError(f"Search failed: {exc}") from exc
