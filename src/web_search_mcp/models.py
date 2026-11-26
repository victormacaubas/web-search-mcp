"""Plain data types shared by the search, retrieval, and tool layers."""

import dataclasses
from typing import Literal

TimeRange = Literal["day", "week", "month", "year"]


@dataclasses.dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclasses.dataclass(frozen=True)
class Retrieved:
    requested_url: str
    final_url: str
    status: int
    content_type: str
    text: str
