from __future__ import annotations

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

FIXTURES = Path(__file__).parent / "fixtures" / "html"
PAGE_URL = "https://docs.example.com/guide/"

HTML_FIXTURES = [
    "main_page.html",
    "no_main_page.html",
    "code_blocks_page.html",
    "table_page.html",
    "links_page.html",
    "app_shell_page.html",
]

MARKDOWN_BODY = (
    "# Title\n\nSee [the API](../api/) for details.\n\n```python\nprint('hi')\n```\n"
)

# Fence languages in the order of the <pre> blocks in code_blocks_page.html.
CODE_BLOCK_LANGUAGES = ["python", "", "", "python", ""]

LINK_TARGET = re.compile(r"\]\(([^)\s]+)\)")


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def parse_fixture(name: str) -> BeautifulSoup:
    return BeautifulSoup(read_fixture(name), "lxml")


def run_extract(content_type: str, body: str, base_url: str = PAGE_URL):
    from web_search_mcp.extract import extract

    return extract(content_type, body, base_url)


def fenced_blocks(markdown: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    lines = markdown.split("\n")
    index = 0
    while index < len(lines):
        if lines[index].startswith("```"):
            language = lines[index][3:].strip()
            body: list[str] = []
            index += 1
            while index < len(lines) and lines[index] != "```":
                body.append(lines[index])
                index += 1
            blocks.append((language, "\n".join(body)))
        index += 1
    return blocks


def table_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


@pytest.mark.parametrize("name", HTML_FIXTURES)
def test_fixture_is_read_by_the_html_parser(name: str) -> None:
    soup = parse_fixture(name)
    assert soup.html is not None
    assert soup.body is not None


def test_main_page_fixture_has_main_nav_header_and_footer() -> None:
    soup = parse_fixture("main_page.html")
    assert soup.main is not None
    assert soup.nav is not None
    assert soup.header is not None
    assert soup.footer is not None


def test_no_main_page_fixture_has_no_main_candidate() -> None:
    soup = parse_fixture("no_main_page.html")
    assert soup.find("main") is None
    assert soup.find("article") is None
    assert soup.find(attrs={"role": "main"}) is None


def test_code_blocks_fixture_has_five_pre_blocks_and_one_with_markup() -> None:
    soup = parse_fixture("code_blocks_page.html")
    pres = soup.find_all("pre")
    assert len(pres) == 5
    assert sum(1 for pre in pres if pre.find("span") is not None) == 1


def test_table_fixture_has_header_row_and_two_data_rows() -> None:
    soup = parse_fixture("table_page.html")
    assert len(soup.find_all("table")) == 1
    assert len(soup.find_all("tr")) == 3


def test_links_fixture_has_relative_link_and_two_permalink_anchors() -> None:
    soup = parse_fixture("links_page.html")
    assert soup.find("a", href="../api/") is not None
    assert len(soup.find_all("a", class_="headerlink")) == 2


def test_app_shell_fixture_is_long_with_little_visible_text() -> None:
    raw = read_fixture("app_shell_page.html")
    assert len(raw) > 10_000
    soup = BeautifulSoup(raw, "lxml")
    for element in soup(["script", "style"]):
        element.decompose()
    assert len(soup.get_text(" ", strip=True)) < 200


def test_markdown_from_server_is_labelled_markdown_from_server() -> None:
    result = run_extract("text/markdown", MARKDOWN_BODY)
    assert result.source == "markdown-from-server"


def test_markdown_from_server_text_is_returned_unchanged() -> None:
    result = run_extract("text/markdown", MARKDOWN_BODY)
    assert result.text == MARKDOWN_BODY


@pytest.mark.parametrize("content_type", ["text/html", "application/xhtml+xml"])
def test_html_is_labelled_converted_from_html(content_type: str) -> None:
    result = run_extract(content_type, read_fixture("main_page.html"))
    assert result.source == "converted-from-html"


@pytest.mark.parametrize(
    "content_type, body",
    [
        ("text/plain", "Plain line one.\nPlain line two.\n"),
        ("application/json", '{"status": "ok", "items": []}'),
        ("application/xml", '<?xml version="1.0"?><feed><entry>one</entry></feed>'),
        ("application/problem+json", '{"title": "Not found", "status": 404}'),
        ("application/atom+xml", "<feed><title>News</title></feed>"),
        ("text/csv", "name,count\nalpha,3\n"),
    ],
)
def test_other_text_types_are_returned_unchanged(content_type: str, body: str) -> None:
    result = run_extract(content_type, body)
    assert result.text == body
    assert result.source == "verbatim"


@pytest.mark.parametrize(
    "content_type",
    ["application/pdf", "image/png", "application/zip"],
)
def test_non_text_type_raises_error_that_names_the_type(content_type: str) -> None:
    from web_search_mcp.extract import ExtractError, extract

    with pytest.raises(ExtractError, match=re.escape(content_type)):
        extract(content_type, "%PDF-1.7 binary body", PAGE_URL)


def test_html_conversion_keeps_article_and_drops_site_navigation() -> None:
    text = run_extract("text/html", read_fixture("main_page.html")).text
    assert "Retry policy" in text
    assert "growing delay" in text
    for navigation_text in ["Pricing", "Careers", "Sign in"]:
        assert navigation_text not in text


def test_header_and_footer_outside_main_are_removed() -> None:
    text = run_extract("text/html", read_fixture("main_page.html")).text
    assert "header banner" not in text
    assert "Copyright notice" not in text


def test_scripts_and_styles_are_removed() -> None:
    text = run_extract("text/html", read_fixture("main_page.html")).text
    assert "window.analytics" not in text
    assert ".site-nav" not in text


def test_html_without_main_region_keeps_body_text() -> None:
    text = run_extract("text/html", read_fixture("no_main_page.html")).text
    assert "Version 2.4 adds a cache" in text
    assert "cache holds at most thirty-two pages" in text


def test_code_blocks_keep_text_and_count_of_source_pre_blocks() -> None:
    soup = parse_fixture("code_blocks_page.html")
    expected = [pre.get_text() for pre in soup.find_all("pre")]
    text = run_extract("text/html", read_fixture("code_blocks_page.html")).text
    blocks = fenced_blocks(text)
    assert len(blocks) == len(expected)
    assert [body for _, body in blocks] == expected


def test_language_class_sets_the_fence_language() -> None:
    text = run_extract("text/html", read_fixture("code_blocks_page.html")).text
    assert [language for language, _ in fenced_blocks(text)] == CODE_BLOCK_LANGUAGES


def test_table_cells_are_kept_as_markdown_table() -> None:
    text = run_extract("text/html", read_fixture("table_page.html")).text
    assert table_rows(text) == [
        ["Parameter", "Type", "Default"],
        ["limit", "integer", "20000"],
        ["offset", "integer", "0"],
    ]


def test_relative_links_become_absolute_against_page_url() -> None:
    text = run_extract("text/html", read_fixture("links_page.html"), PAGE_URL).text
    assert set(LINK_TARGET.findall(text)) == {
        "https://docs.example.com/api/",
        "https://docs.example.com/guide/setup/",
        "https://docs.example.com/settings",
        "https://example.org/changelog",
    }


def test_heading_permalink_anchors_are_removed() -> None:
    text = run_extract("text/html", read_fixture("links_page.html")).text
    assert "¶" not in text
    assert "#install" not in text
    assert "#configure" not in text
    assert "Install" in text
    assert "Configure" in text


def test_app_shell_page_gets_javascript_warning() -> None:
    result = run_extract("text/html", read_fixture("app_shell_page.html"))
    assert any("JavaScript" in warning for warning in result.warnings)


def test_page_with_main_region_gets_no_warning() -> None:
    result = run_extract("text/html", read_fixture("main_page.html"))
    assert result.warnings == ()


@pytest.mark.parametrize("name", HTML_FIXTURES)
def test_converted_output_has_at_most_two_empty_lines_in_a_row(name: str) -> None:
    text = run_extract("text/html", read_fixture(name)).text
    assert "\n\n\n\n" not in text


def test_code_block_keeps_three_consecutive_empty_lines() -> None:
    code = "def first():\n    return 1\n\n\n\ndef second():\n    return 2"
    html = (
        "<!DOCTYPE html><html><body><main>"
        f"<pre><code>{code}</code></pre>"
        "</main></body></html>"
    )
    expected = BeautifulSoup(html, "lxml").find("pre").get_text()
    assert "\n\n\n\n" in expected
    blocks = fenced_blocks(run_extract("text/html", html).text)
    assert [body for _, body in blocks] == [expected]


def test_blank_lines_outside_code_block_are_reduced_to_two() -> None:
    html = (
        "<!DOCTYPE html><html><body><main>"
        "<p>Install the package.</p><ul></ul><ul></ul><p>Then run the tool.</p>"
        "</main></body></html>"
    )
    text = run_extract("text/html", html).text
    assert "Install the package.\n\n\nThen run the tool." in text
    assert "\n\n\n\n" not in text
