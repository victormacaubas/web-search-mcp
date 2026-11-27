"""Selects the text pipeline for a content type and converts HTML to markdown."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

if TYPE_CHECKING:
    from bs4.element import Tag

Source = Literal["markdown-from-server", "converted-from-html", "verbatim"]

HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
VERBATIM_TYPES = frozenset({"application/json", "application/xml"})
VERBATIM_SUFFIXES = ("+json", "+xml")

SPARSE_HTML_MIN_CHARS = 10_000
SPARSE_TEXT_MAX_CHARS = 200
SPARSE_PAGE_WARNING = (
    "The page has little text for its size. It possibly needs JavaScript, "
    "so the text can be incomplete."
)

REGION_SELECTOR = "main, article, [role=main]"
ALWAYS_REMOVED_SELECTOR = ", ".join(
    [
        "script",
        "style",
        "noscript",
        "template",
        "svg",
        "iframe",
        "nav",
        "aside",
        "form",
        "button",
        "[role=navigation]",
        "[role=banner]",
        "[role=contentinfo]",
        "[role=search]",
    ]
)
PERMALINK_TEXTS = frozenset({"¶", "#"})
CODE_LANGUAGE_CLASS = re.compile(r"^(?:language|highlight)-(?:source-)?([\w+#.-]+)$")
UNSET_LANGUAGES = frozenset({"default", "none"})
EXCESS_BLANK_LINES = re.compile(r"\n{4,}")
FENCED_CODE_BLOCK = re.compile(r"(^```[^\n]*\n.*?\n```$)", re.DOTALL | re.MULTILINE)


class ExtractError(Exception):
    """The content type has no text form that the tool can return."""


@dataclass(frozen=True)
class Extracted:
    text: str
    source: Source
    warnings: tuple[str, ...]


def extract(content_type: str, body: str, base_url: str) -> Extracted:
    """Turn a response body into page text according to its content type.

    Args:
        content_type: Lowercase media type with no parameters.
        body: Decoded response body.
        base_url: Final URL of the page, used to make links absolute.

    Raises:
        ExtractError: The content type is not a text type.
    """
    if content_type == "text/markdown":
        return Extracted(body, "markdown-from-server", ())
    if content_type in HTML_TYPES:
        text = html_to_markdown(body, base_url)
        sparse = len(body) > SPARSE_HTML_MIN_CHARS and len(text) < SPARSE_TEXT_MAX_CHARS
        warnings = (SPARSE_PAGE_WARNING,) if sparse else ()
        return Extracted(text, "converted-from-html", warnings)
    if _is_verbatim_type(content_type):
        return Extracted(body, "verbatim", ())
    raise ExtractError(f"Content type {content_type} is not text and cannot be read.")


def html_to_markdown(html: str, base_url: str) -> str:
    """Convert the main region of an HTML page to markdown."""
    soup = BeautifulSoup(html, "lxml")
    region = _select_region(soup)
    _remove_noise(region)
    _remove_permalinks(region)
    _make_urls_absolute(region, base_url)
    converter = MarkdownConverter(
        heading_style="ATX", code_language_callback=_code_language
    )
    text = converter.convert_soup(region)
    return _limit_blank_lines(text.replace("\r\n", "\n")).strip()


def _limit_blank_lines(text: str) -> str:
    # re.split with one capture group puts fenced blocks at the odd indexes.
    parts = FENCED_CODE_BLOCK.split(text)
    for index in range(0, len(parts), 2):
        parts[index] = EXCESS_BLANK_LINES.sub("\n\n\n", parts[index])
    return "".join(parts)


def _is_verbatim_type(content_type: str) -> bool:
    return (
        content_type.startswith("text/")
        or content_type in VERBATIM_TYPES
        or content_type.endswith(VERBATIM_SUFFIXES)
    )


def _select_region(soup: BeautifulSoup) -> Tag:
    candidates = soup.select(REGION_SELECTOR)
    if candidates:
        return max(candidates, key=lambda tag: len(tag.get_text(strip=True)))
    return soup.body or soup


def _remove_noise(region: Tag) -> None:
    for element in region.select(ALWAYS_REMOVED_SELECTOR):
        element.decompose()
    for element in region.select("header, footer"):
        # Descendants of an element removed above are already decomposed.
        if element.decomposed:
            continue
        if element.find_parent(["main", "article"]) is None:
            element.decompose()


def _remove_permalinks(region: Tag) -> None:
    for anchor in region.select("a"):
        if anchor.decomposed:
            continue
        classes = anchor.get_attribute_list("class")
        if "headerlink" in classes or anchor.get_text(strip=True) in PERMALINK_TEXTS:
            anchor.decompose()


def _make_urls_absolute(region: Tag, base_url: str) -> None:
    for anchor in region.select("a[href]"):
        with contextlib.suppress(ValueError):
            anchor["href"] = urljoin(base_url, str(anchor["href"]))
    for image in region.select("img[src]"):
        with contextlib.suppress(ValueError):
            image["src"] = urljoin(base_url, str(image["src"]))


def _code_language(pre: Tag) -> str | None:
    code = pre.find("code")
    holders = [pre, *([code] if code is not None else []), *pre.parents]
    for holder in holders:
        for css_class in holder.get_attribute_list("class"):
            match = CODE_LANGUAGE_CLASS.match(css_class)
            if match and match.group(1) not in UNSET_LANGUAGES:
                return match.group(1)
    return None
