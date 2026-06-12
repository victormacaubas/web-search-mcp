from __future__ import annotations

import pytest
from pydantic import ValidationError

from web_search_mcp.models import WebSearchInput


def test_valid_input_applies_defaults() -> None:
    params = WebSearchInput(query="hello")
    assert params.query == "hello"
    assert params.max_results == 5
    assert params.region is None


def test_query_whitespace_is_stripped() -> None:
    params = WebSearchInput(query="  hello  ")
    assert params.query == "hello"


def test_empty_query_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        WebSearchInput(query="")


def test_whitespace_only_query_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        WebSearchInput(query="   ")


def test_max_results_below_minimum_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        WebSearchInput(query="hello", max_results=0)


def test_max_results_above_maximum_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        WebSearchInput(query="hello", max_results=21)


def test_max_results_at_boundaries_are_valid() -> None:
    low = WebSearchInput(query="hello", max_results=1)
    assert low.max_results == 1

    high = WebSearchInput(query="hello", max_results=20)
    assert high.max_results == 20


def test_region_none_is_valid() -> None:
    params = WebSearchInput(query="hello", region=None)
    assert params.region is None


def test_region_string_is_valid() -> None:
    params = WebSearchInput(query="hello", region="us-en")
    assert params.region == "us-en"
