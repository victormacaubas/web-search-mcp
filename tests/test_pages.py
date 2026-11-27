from __future__ import annotations

import asyncio
import gc
import re
from datetime import UTC, datetime, timedelta

import pytest

from tests.fetch_fakes import HEADER_LABELS, MATCHES_DELIMITER, PAGE_DELIMITER
from web_search_mcp.models import Retrieved
from web_search_mcp.pages import (
    Heading,
    PageError,
    PageStore,
    Snapshot,
    find_headings,
    find_text,
    outline,
    part_bounds,
    render_find,
    render_part,
)

REQUESTED_URL = "https://docs.example.com/guide"
FINAL_URL = "https://docs.example.com/guide/"
RETRIEVED_AT = datetime(2026, 11, 26, 18, 20, 11, tzinfo=UTC)
START = datetime(2026, 11, 26, 18, 0, 0, tzinfo=UTC)
OUTLINE_LINE = re.compile(r"^\s*(\d+)\s+(#{1,6}) (.+)$")


class RetrievalFailedError(Exception):
    pass


class FakeClock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, *, minutes: int) -> None:
        self.now = self.now + timedelta(minutes=minutes)


class FakeRetriever:
    def __init__(self, *, failures: int = 0, gate: asyncio.Event | None = None) -> None:
        self.requested: list[str] = []
        self._failures = failures
        self._gate = gate

    async def __call__(self, url: str) -> Retrieved:
        self.requested.append(url)
        if self._gate is not None:
            await self._gate.wait()
        if self._failures > 0:
            self._failures -= 1
            raise RetrievalFailedError(url)
        return Retrieved(
            requested_url=url,
            final_url=url,
            status=200,
            content_type="text/markdown",
            text=f"# Page\n\nBody for {url}\n",
        )


def make_snapshot(text: str, warnings: tuple[str, ...] = ()) -> Snapshot:
    return Snapshot(
        url=REQUESTED_URL,
        final_url=FINAL_URL,
        status=200,
        source="markdown-from-server",
        text=text,
        retrieved_at=RETRIEVED_AT,
        headings=tuple(find_headings(text)),
        warnings=warnings,
    )


def join_lines(lines: list[str]) -> tuple[str, list[int]]:
    text = ""
    starts: list[int] = []
    for line in lines:
        starts.append(len(text))
        text += line + "\n"
    return text, starts


def split_at(rendered: str, delimiter: str) -> tuple[str, str]:
    head, marker, tail = rendered.partition(delimiter)
    assert marker == delimiter, f"delimiter not found: {delimiter}"
    return head, tail


def header_fields(head: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in head.splitlines():
        if line.startswith(" "):
            continue
        key, sep, value = line.partition(": ")
        if sep:
            fields[key] = value
    return fields


def outline_entries(head: str) -> list[tuple[int, str, str]]:
    entries: list[tuple[int, str, str]] = []
    for line in head.splitlines():
        found = OUTLINE_LINE.match(line)
        if found:
            entries.append((int(found.group(1)), found.group(2), found.group(3)))
    return entries


def heading_blocks(count: int) -> tuple[str, list[tuple[int, str, str]]]:
    text = ""
    expected: list[tuple[int, str, str]] = []
    for i in range(count):
        expected.append((len(text), "##", f"Heading {i}"))
        text += f"## Heading {i}\n" + "body text\n" * 20
    return text, expected


MATCH_TEXT_LINES = [
    "first section",
    "before one",
    "needle one",
    "after one",
    "middle",
    "before two",
    "needle two",
    "after two",
    "middle",
    "before three",
    "needle three",
    "after three",
]


# Parts, header and delimiter (task 7.1)


def test_default_part_is_at_most_twenty_thousand_characters_from_offset_zero() -> None:
    text = "a" * 96_000
    assert part_bounds(text, 0, 20_000) == (0, 20_000)


@pytest.mark.parametrize(
    ("text", "expected_end"),
    [
        ("a" * 15_000 + "\n" + "b" * 90_000, 15_001),
        ("a" * 12_000 + "\n" + "b" * 5_000 + "\n" + "c" * 90_000, 17_002),
    ],
    ids=["one-line-end-in-last-half", "last-of-two-line-ends-in-last-half"],
)
def test_part_ends_after_last_line_end_in_last_half_of_range(
    text: str, expected_end: int
) -> None:
    assert part_bounds(text, 0, 20_000) == (0, expected_end)


@pytest.mark.parametrize(
    "text",
    [
        "a" * 96_000,
        "a" * 5_000 + "\n" + "b" * 90_000,
    ],
    ids=["no-line-end", "line-end-only-in-first-half"],
)
def test_range_without_line_end_in_last_half_is_cut_at_limit(text: str) -> None:
    assert part_bounds(text, 0, 20_000) == (0, 20_000)


@pytest.mark.parametrize("limit", [20_000, 1_000])
def test_consecutive_parts_cover_the_page_exactly_once(limit: int) -> None:
    text = "\n".join(f"line {i}: " + "x" * (i % 97) for i in range(2_000))
    assert len(text) > 96_000

    offset = 0
    bounds: list[tuple[int, int]] = []
    while True:
        assert len(bounds) <= len(text), "parts never reach the end of the page"
        start, end = part_bounds(text, offset, limit)
        assert start == offset
        assert end > start
        bounds.append((start, end))
        if end >= len(text):
            break
        offset = end

    assert bounds[-1][1] == len(text)
    for (_, previous_end), (next_start, _) in zip(bounds, bounds[1:], strict=False):
        assert next_start == previous_end
    assert all(end - start <= limit for start, end in bounds)
    assert "".join(text[start:end] for start, end in bounds) == text


@pytest.mark.parametrize("offset", [96_510, 96_511])
def test_offset_at_or_after_end_is_error_that_states_total_length(offset: int) -> None:
    text = "x" * 96_510
    with pytest.raises(PageError) as info:
        part_bounds(text, offset, 20_000)
    assert "total length 96510" in str(info.value)


def test_empty_page_part_at_offset_zero_is_empty_range() -> None:
    assert part_bounds("", 0, 20_000) == (0, 0)


def test_empty_page_at_offset_zero_renders_zero_range_end_of_page_and_warning() -> None:
    warning = "page text is empty"
    rendered = render_part(make_snapshot("", warnings=(warning,)), 0, 20_000)
    head, tail = split_at(rendered, PAGE_DELIMITER)
    fields = header_fields(head)
    assert fields["total_chars"] == "0"
    assert fields["range"] == "0-0"
    assert fields["next_offset"] == "none (end of page)"
    assert fields["warnings"] == warning
    assert tail == "\n"


def test_result_for_full_page_header_states_total_range_and_end_of_page() -> None:
    text = "# Short page\n\nA few words.\n"
    rendered = render_part(make_snapshot(text), 0, 20_000)
    head, tail = split_at(rendered, PAGE_DELIMITER)
    assert rendered.splitlines()[0] == f"url: {REQUESTED_URL}"
    fields = header_fields(head)
    assert fields["final_url"] == FINAL_URL
    assert fields["status"] == "200"
    assert fields["source"] == "markdown-from-server"
    assert fields["retrieved_at"] == "2026-11-26T18:20:11Z"
    assert fields["total_chars"] == str(len(text))
    assert fields["range"] == f"0-{len(text)}"
    assert fields["next_offset"] == "none (end of page)"
    assert fields["warnings"] == "none"


def test_result_for_part_header_states_total_range_and_next_offset() -> None:
    text = "a" * 96_000
    rendered = render_part(make_snapshot(text), 0, 20_000)
    head, _ = split_at(rendered, PAGE_DELIMITER)
    fields = header_fields(head)
    assert fields["total_chars"] == "96000"
    assert fields["range"] == "0-20000"
    assert fields["next_offset"] == "20000"


def test_delimiter_appears_once_after_header_and_text_follows_unchanged() -> None:
    text = "Mixed text with *markdown* and `code`. " * 2_000
    assert len(text) > 20_000
    rendered = render_part(make_snapshot(text), 0, 20_000)
    assert rendered.count(PAGE_DELIMITER) == 1
    head, tail = split_at(rendered, PAGE_DELIMITER)
    fields = header_fields(head)
    for label in HEADER_LABELS:
        assert label in fields
    assert tail == "\n" + text[:20_000]


# Outline (task 7.3)


def test_find_headings_gives_level_title_and_offset_of_line_start() -> None:
    text, starts = join_lines(
        ["# Title", "intro", "## Section", "body", "### Detail", "end"]
    )
    headings = find_headings(text)
    assert [(h.level, h.title, h.offset) for h in headings] == [
        (1, "Title", starts[0]),
        (2, "Section", starts[2]),
        (3, "Detail", starts[4]),
    ]


def test_comment_line_inside_fenced_code_block_is_not_in_outline() -> None:
    lines = ["# Intro", "", "```", "# Expected output:", "```", "", "## After"]
    text, _ = join_lines(lines + ["filler text"] * 2_000)
    rendered = render_part(make_snapshot(text), 0, 20_000)
    head, _ = split_at(rendered, PAGE_DELIMITER)
    assert "Expected output" not in head
    assert [title for _, _, title in outline_entries(head)] == ["Intro", "After"]


def test_single_line_triple_backtick_code_span_does_not_hide_later_headings() -> None:
    lines = ["# Title", "``` ``foo`` ```", "## Section 2"]
    text, starts = join_lines(lines)
    headings = find_headings(text)
    assert [(h.level, h.title, h.offset) for h in headings] == [
        (1, "Title", starts[0]),
        (2, "Section 2", starts[2]),
    ]


def test_result_with_full_page_has_no_outline() -> None:
    text = "# Title\n\n## Section\n\nbody\n"
    rendered = render_part(make_snapshot(text), 0, 20_000)
    head, _ = split_at(rendered, PAGE_DELIMITER)
    assert "outline:" not in head
    assert outline_entries(head) == []


def test_result_at_nonzero_offset_has_no_outline() -> None:
    text, _ = join_lines(["# Title", "## Section"] + ["filler text"] * 2_000)
    rendered = render_part(make_snapshot(text), 100, 20_000)
    head, _ = split_at(rendered, PAGE_DELIMITER)
    assert "outline:" not in head
    assert outline_entries(head) == []


def test_long_page_outline_lists_headings_with_offsets_including_late_ones() -> None:
    lines = (
        ["# Guide"]
        + ["filler text"] * 10
        + ["## Setup"]
        + ["filler text"] * 10
        + ["filler text"] * 2_000
        + ["## Late section"]
        + ["filler text"] * 10
    )
    text, starts = join_lines(lines)
    rendered = render_part(make_snapshot(text), 0, 20_000)
    head, _ = split_at(rendered, PAGE_DELIMITER)
    assert outline_entries(head) == [
        (starts[0], "#", "Guide"),
        (starts[lines.index("## Setup")], "##", "Setup"),
        (starts[lines.index("## Late section")], "##", "Late section"),
    ]


def test_outline_with_174_headings_has_50_entries_and_states_headings_left_out() -> (
    None
):
    text, expected = heading_blocks(174)
    rendered = render_part(make_snapshot(text), 0, 20_000)
    head, _ = split_at(rendered, PAGE_DELIMITER)
    assert outline_entries(head) == expected[:50]
    assert any("left out" in line for line in head.splitlines())


def test_outline_keeps_first_fifty_headings_when_one_level_is_over_the_limit() -> None:
    headings = [Heading(level=2, title=f"h{i}", offset=i * 10) for i in range(174)]
    kept, left_out = outline(headings)
    assert [h.title for h in kept] == [f"h{i}" for i in range(50)]
    assert left_out == 124


@pytest.mark.parametrize(
    ("levels", "deepest_kept", "expected_kept", "expected_left_out"),
    [
        ([1] * 10 + [2] * 40 + [3] * 30, 2, 50, 30),
        ([1] * 5 + [2] * 60 + [3] * 30, 1, 5, 90),
    ],
    ids=["deepest-level-removed", "two-levels-removed"],
)
def test_outline_removes_deepest_level_until_fifty_or_fewer_remain(
    levels: list[int],
    deepest_kept: int,
    expected_kept: int,
    expected_left_out: int,
) -> None:
    headings = [
        Heading(level=level, title=f"h{i}", offset=i) for i, level in enumerate(levels)
    ]
    kept, left_out = outline(headings)
    assert len(kept) == expected_kept
    assert left_out == expected_left_out
    assert [h.title for h in kept] == [
        h.title for h in headings if h.level <= deepest_kept
    ]


# Find (task 7.4)


def test_find_result_lists_matches_with_line_start_offsets_and_surrounding_lines() -> (
    None
):
    text, starts = join_lines(MATCH_TEXT_LINES)
    rendered = render_find(make_snapshot(text), "needle", 0)
    head, _ = split_at(rendered, MATCHES_DELIMITER)
    assert rendered.count(MATCHES_DELIMITER) == 1
    assert header_fields(head)["matches"] == "3 of 3"
    assert re.findall(r"^@(\d+)", rendered, re.MULTILINE) == [
        str(starts[index]) for index in (2, 6, 10)
    ]
    for index in (2, 6, 10):
        for neighbour in (index - 1, index, index + 1):
            assert MATCH_TEXT_LINES[neighbour] in rendered


@pytest.mark.parametrize("needle", ["alpha", "ALPHA", "AlPhA"])
def test_find_ignores_letter_case(needle: str) -> None:
    text, starts = join_lines(
        ["Alpha at top", "plain line", "alpha in middle", "no match", "ALPHA at end"]
    )
    result = find_text(text, needle)
    assert result.total == 3
    assert [m.offset for m in result.matches] == [starts[0], starts[2], starts[4]]


def test_find_without_matches_states_that_full_page_was_searched() -> None:
    text = "# Notes\n\nNothing relevant here.\n"
    rendered = render_find(make_snapshot(text), "absent phrase", 0)
    head, _ = split_at(rendered, MATCHES_DELIMITER)
    fields = header_fields(head)
    assert fields["matches"] == "0 of 0"
    assert fields["searched"] == f"0-{len(text)} (full page text)"
    assert fields["next_offset"] == "none (all matches shown)"


def test_find_returns_first_twenty_matches_with_total_and_offset_to_continue() -> None:
    text, starts = join_lines([f"entry {i:02d} needle" for i in range(45)])
    result = find_text(text, "needle")
    assert result.total == 45
    assert [m.offset for m in result.matches] == starts[:20]
    assert result.next_offset == starts[20]

    rendered = render_find(make_snapshot(text), "needle", 0)
    head, _ = split_at(rendered, MATCHES_DELIMITER)
    fields = header_fields(head)
    assert fields["matches"] == "20 of 45"
    assert fields["next_offset"] == str(starts[20])
    assert re.findall(r"^@(\d+)", rendered, re.MULTILINE) == [
        str(offset) for offset in starts[:20]
    ]

    continued = find_text(text, "needle", offset=starts[20])
    assert continued.matches[0].offset == starts[20]


def test_part_read_from_match_offset_starts_with_the_matching_line() -> None:
    text, starts = join_lines(MATCH_TEXT_LINES)
    rendered = render_part(make_snapshot(text), starts[6], 20_000)
    _, tail = split_at(rendered, PAGE_DELIMITER)
    assert tail.startswith("\n" + MATCH_TEXT_LINES[6] + "\n")


@pytest.mark.parametrize("offset", [10, 11])
def test_find_offset_at_or_after_end_is_error_that_states_total_length(
    offset: int,
) -> None:
    snapshot = make_snapshot("0123456789")
    with pytest.raises(PageError, match="total length 10"):
        render_find(snapshot, "0", offset)


# Snapshot store (task 7.5)


async def test_second_call_within_fifteen_minutes_reuses_the_retrieval() -> None:
    clock = FakeClock()
    retriever = FakeRetriever()
    store = PageStore(retriever, clock=clock)
    first = await store.get(REQUESTED_URL)
    clock.advance(minutes=14)
    second = await store.get(REQUESTED_URL)
    assert len(retriever.requested) == 1
    assert second.retrieved_at == first.retrieved_at


async def test_call_after_fifteen_minutes_makes_a_new_retrieval() -> None:
    clock = FakeClock()
    retriever = FakeRetriever()
    store = PageStore(retriever, clock=clock)
    await store.get(REQUESTED_URL)
    clock.advance(minutes=16)
    second = await store.get(REQUESTED_URL)
    assert len(retriever.requested) == 2
    assert second.retrieved_at == clock()


async def test_url_with_fragment_shares_the_snapshot_of_the_url_without_fragment() -> (
    None
):
    clock = FakeClock()
    retriever = FakeRetriever()
    store = PageStore(retriever, clock=clock)
    await store.get("https://example.com/page")
    await store.get("https://example.com/page#section")
    assert retriever.requested == ["https://example.com/page"]


async def test_failed_retrieval_is_not_stored_and_the_next_call_retries() -> None:
    clock = FakeClock()
    retriever = FakeRetriever(failures=1)
    store = PageStore(retriever, clock=clock)
    with pytest.raises(RetrievalFailedError):
        await store.get(REQUESTED_URL)
    await store.get(REQUESTED_URL)
    assert len(retriever.requested) == 2


async def test_store_keeps_at_most_32_snapshots_and_evicts_least_recently_used() -> (
    None
):
    clock = FakeClock()
    retriever = FakeRetriever()
    store = PageStore(retriever, clock=clock)
    urls = [f"https://example.com/page-{i}" for i in range(33)]
    for url in urls[:32]:
        await store.get(url)
    assert len(retriever.requested) == 32

    await store.get(urls[0])
    assert len(retriever.requested) == 32

    await store.get(urls[32])
    assert len(retriever.requested) == 33

    # urls[0] was used after the others, so urls[1] is the least recently used.
    await store.get(urls[0])
    assert len(retriever.requested) == 33

    await store.get(urls[1])
    assert len(retriever.requested) == 34


async def test_concurrent_calls_for_one_url_make_one_retrieval() -> None:
    clock = FakeClock()
    gate = asyncio.Event()
    retriever = FakeRetriever(gate=gate)
    store = PageStore(retriever, clock=clock)
    tasks = [asyncio.create_task(store.get(REQUESTED_URL)) for _ in range(5)]
    # Lets the other calls reach the store while the retrieval waits on the gate.
    for _ in range(10):
        await asyncio.sleep(0)
    gate.set()
    snapshots: list[Snapshot] = list(await asyncio.gather(*tasks))
    assert len(retriever.requested) == 1
    assert all(s.retrieved_at == snapshots[0].retrieved_at for s in snapshots)


async def test_cancelled_caller_does_not_leave_unretrieved_task_exception() -> None:
    clock = FakeClock()
    gate = asyncio.Event()
    retriever = FakeRetriever(failures=1, gate=gate)
    store = PageStore(retriever, clock=clock)

    loop = asyncio.get_running_loop()
    unhandled: list[dict[str, object]] = []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, ctx: unhandled.append(ctx))
    try:
        caller = asyncio.create_task(store.get(REQUESTED_URL))
        await asyncio.sleep(0)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller

        gate.set()
        for _ in range(5):
            await asyncio.sleep(0)
        gc.collect()
    finally:
        loop.set_exception_handler(previous_handler)

    assert unhandled == []
    # The failed load was not stored, so a follow-up call retries and succeeds.
    snapshot = await store.get(REQUESTED_URL)
    assert snapshot.url == REQUESTED_URL
    assert len(retriever.requested) == 2
