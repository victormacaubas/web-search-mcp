import dataclasses

from pydantic import BaseModel, ConfigDict, Field


@dataclasses.dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)
    region: str | None = Field(default=None)
