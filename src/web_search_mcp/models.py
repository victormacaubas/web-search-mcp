import dataclasses

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("query")
    @classmethod
    def reject_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be whitespace-only")
        return v
