from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import httpx
import pytest

from tests.fetch_fakes import (
    PUBLIC_IPV4,
    PUBLIC_IPV4_OTHER,
    FakeResolver,
    FakeSite,
    RebindingResolver,
)
from web_search_mcp.fetch import FetchError, retrieve

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from web_search_mcp.models import Retrieved

MB = 1024 * 1024
RESPONSE_TEXT_TYPE = "text/plain"


def _redirect(location: str) -> httpx.Response:
    return httpx.Response(302, headers={"location": location})


def _text(body: str) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": RESPONSE_TEXT_TYPE}, text=body)


async def _fetch(
    url: str,
    site: FakeSite,
    resolver: FakeResolver | RebindingResolver,
    **options: float | int,
) -> Retrieved:
    async with httpx.AsyncClient(transport=httpx.MockTransport(site.handle)) as client:
        return await retrieve(url, client=client, resolver=resolver, **options)


def _media_q_values(accept: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for part in accept.split(","):
        pieces = [piece.strip() for piece in part.split(";")]
        quality = 1.0
        for parameter in pieces[1:]:
            if parameter.startswith("q="):
                quality = float(parameter[2:])
        values[pieces[0].lower()] = quality
    return values


def _hop_route(hops: int) -> Callable[[httpx.Request], httpx.Response]:
    def route(request: httpx.Request) -> httpx.Response:
        position = int(request.url.path.rsplit("/", 1)[-1])
        if position >= hops:
            return _text("end of chain")
        return _redirect(f"https://chain.example.test/hop/{position + 1}")

    return route


class _StreamedBody(httpx.AsyncByteStream):
    """A response body that yields chunks on demand and counts the bytes yielded."""

    def __init__(self, total: int, chunk_size: int) -> None:
        self.total = total
        self.chunk_size = chunk_size
        self.bytes_yielded = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        while self.bytes_yielded < self.total:
            self.bytes_yielded += self.chunk_size
            yield b"a" * self.chunk_size


async def test_accept_header_asks_for_markdown_ahead_of_html() -> None:
    accept_headers: list[str] = []

    def route(request: httpx.Request) -> httpx.Response:
        accept_headers.append(request.headers["accept"])
        return _text("ok")

    site = FakeSite({"docs.example.test": route})
    await _fetch(
        "https://docs.example.test/page",
        site,
        FakeResolver({"docs.example.test": [PUBLIC_IPV4]}),
    )

    values = _media_q_values(accept_headers[0])
    assert "text/markdown" in values
    assert values.get("text/html", 0.0) < values["text/markdown"]


async def test_user_agent_starts_with_project_name() -> None:
    user_agents: list[str] = []

    def route(request: httpx.Request) -> httpx.Response:
        user_agents.append(request.headers["user-agent"])
        return _text("ok")

    site = FakeSite({"agent.example.test": route})
    await _fetch(
        "https://agent.example.test/",
        site,
        FakeResolver({"agent.example.test": [PUBLIC_IPV4]}),
    )

    assert user_agents[0].startswith("web-search-mcp/")


async def test_redirect_to_other_host_is_followed_and_reported_as_final_url() -> None:
    site = FakeSite(
        {
            "old.example.com": lambda request: _redirect(
                "https://new.example.org/page"
            ),
            "new.example.org": lambda request: _text("page at the new host"),
        }
    )
    resolver = FakeResolver(
        {
            "old.example.com": [PUBLIC_IPV4],
            "new.example.org": [PUBLIC_IPV4_OTHER],
        }
    )

    retrieved = await _fetch("https://old.example.com/page", site, resolver)

    assert retrieved.requested_url == "https://old.example.com/page"
    assert retrieved.final_url == "https://new.example.org/page"
    assert retrieved.status == 200
    assert retrieved.text == "page at the new host"


async def test_exactly_five_redirects_are_followed() -> None:
    site = FakeSite({"chain.example.test": _hop_route(5)})

    retrieved = await _fetch(
        "https://chain.example.test/hop/0",
        site,
        FakeResolver({"chain.example.test": [PUBLIC_IPV4]}),
    )

    assert retrieved.final_url == "https://chain.example.test/hop/5"
    assert retrieved.status == 200
    assert retrieved.text == "end of chain"


async def test_sixth_redirect_is_refused_with_redirect_limit_error() -> None:
    site = FakeSite({"chain.example.test": _hop_route(6)})

    with pytest.raises(FetchError, match="redirect limit"):
        await _fetch(
            "https://chain.example.test/hop/0",
            site,
            FakeResolver({"chain.example.test": [PUBLIC_IPV4]}),
        )


async def test_redirect_to_private_address_is_refused_without_request_to_it() -> None:
    site = FakeSite(
        {"public.example.test": lambda request: _redirect("http://192.168.1.1/admin")}
    )

    with pytest.raises(FetchError, match="not a public address"):
        await _fetch(
            "https://public.example.test/start",
            site,
            FakeResolver({"public.example.test": [PUBLIC_IPV4]}),
        )

    assert "192.168.1.1" not in site.hosts_contacted()


async def test_guard_refusal_of_loopback_url_is_fetch_error_without_request() -> None:
    site = FakeSite({"127.0.0.1": lambda request: _text("must not be fetched")})

    with pytest.raises(FetchError, match="not a public address"):
        await _fetch("http://127.0.0.1/", site, FakeResolver({}))

    assert site.requests == []


async def test_rebinding_host_name_is_connected_only_at_checked_address() -> None:
    resolver = RebindingResolver()
    site = FakeSite({"rebind.example.test": lambda request: _text("public page")})

    # The spec allows either a fetch at the checked address or a refusal.
    with contextlib.suppress(FetchError):
        await _fetch("https://rebind.example.test/", site, resolver)

    assert len(resolver.calls) == 1
    hosts = site.hosts_contacted()
    assert "127.0.0.1" not in hosts
    assert set(hosts) <= {PUBLIC_IPV4}


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("file:///etc/hosts", id="file-scheme"),
        pytest.param("ftp://public.example.test/file.txt", id="ftp-scheme"),
        pytest.param(
            "https://user:secret@public.example.test/", id="user-and-password"
        ),
    ],
)
async def test_unsupported_scheme_or_credentials_are_refused_before_any_request(
    url: str,
) -> None:
    site = FakeSite(
        {"public.example.test": lambda request: _text("must not be fetched")}
    )

    with pytest.raises(FetchError):
        await _fetch(url, site, FakeResolver({"public.example.test": [PUBLIC_IPV4]}))

    assert site.requests == []


async def test_body_past_size_limit_is_cut_off_with_size_error() -> None:
    body = _StreamedBody(total=20 * MB, chunk_size=64 * 1024)
    site = FakeSite(
        {
            "big.example.test": lambda request: httpx.Response(
                200, headers={"content-type": RESPONSE_TEXT_TYPE}, stream=body
            )
        }
    )

    with pytest.raises(FetchError, match="5 MB"):
        await _fetch(
            "https://big.example.test/file",
            site,
            FakeResolver({"big.example.test": [PUBLIC_IPV4]}),
        )

    assert body.bytes_yielded < 20 * MB


async def test_slow_response_gives_time_limit_error() -> None:
    async def stall(request: httpx.Request) -> httpx.Response:
        # The time limit cancels this wait. The ceiling stops a hung build.
        await asyncio.sleep(10)
        return _text("late")

    site = FakeSite({"slow.example.test": stall})

    with pytest.raises(FetchError, match="time limit"):
        await _fetch(
            "https://slow.example.test/",
            site,
            FakeResolver({"slow.example.test": [PUBLIC_IPV4]}),
            timeout=0.2,
        )


async def test_status_404_error_states_status_and_final_url() -> None:
    site = FakeSite(
        {"missing.example.test": lambda request: httpx.Response(404, text="not here")}
    )

    with pytest.raises(FetchError) as info:
        await _fetch(
            "https://missing.example.test/gone",
            site,
            FakeResolver({"missing.example.test": [PUBLIC_IPV4]}),
        )

    message = str(info.value)
    assert "status 404" in message
    assert "https://missing.example.test/gone" in message


async def test_status_429_error_states_status_and_retry_after() -> None:
    site = FakeSite(
        {
            "limited.example.test": lambda request: httpx.Response(
                429, headers={"retry-after": "60"}, text="slow down"
            )
        }
    )

    with pytest.raises(FetchError) as info:
        await _fetch(
            "https://limited.example.test/",
            site,
            FakeResolver({"limited.example.test": [PUBLIC_IPV4]}),
        )

    message = str(info.value)
    assert "status 429" in message
    assert "Retry-After: 60" in message


async def test_status_403_error_states_retry_after() -> None:
    site = FakeSite(
        {
            "guarded.example.test": lambda request: httpx.Response(
                403, headers={"retry-after": "120"}, text="forbidden"
            )
        }
    )

    with pytest.raises(FetchError) as info:
        await _fetch(
            "https://guarded.example.test/",
            site,
            FakeResolver({"guarded.example.test": [PUBLIC_IPV4]}),
        )

    message = str(info.value)
    assert "status 403" in message
    assert "Retry-After: 120" in message


@pytest.mark.parametrize(
    "status",
    [pytest.param(429, id="status-429"), pytest.param(403, id="status-403")],
)
async def test_rate_limit_headers_are_stated_in_error(status: int) -> None:
    site = FakeSite(
        {
            "quota.example.test": lambda request: httpx.Response(
                status,
                headers={
                    "x-ratelimit-remaining": "250",
                    "x-ratelimit-reset": "1798761600",
                },
                text="quota exceeded",
            )
        }
    )

    with pytest.raises(FetchError) as info:
        await _fetch(
            "https://quota.example.test/",
            site,
            FakeResolver({"quota.example.test": [PUBLIC_IPV4]}),
        )

    message = str(info.value).lower()
    assert "x-ratelimit-remaining" in message
    assert "250" in message
    assert "x-ratelimit-reset" in message
    assert "1798761600" in message


async def test_network_failure_error_states_failure_type() -> None:
    def refuse_connection(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    site = FakeSite({"down.example.test": refuse_connection})

    with pytest.raises(FetchError) as info:
        await _fetch(
            "https://down.example.test/",
            site,
            FakeResolver({"down.example.test": [PUBLIC_IPV4]}),
        )

    assert "connect" in str(info.value).lower()


async def test_host_name_that_does_not_resolve_is_reported_as_not_resolved() -> None:
    site = FakeSite({})

    with pytest.raises(FetchError, match="not resolved"):
        await _fetch("https://nowhere.example.test/", site, FakeResolver({}))

    assert site.requests == []


async def test_content_type_is_lowercase_media_type_without_parameters() -> None:
    site = FakeSite(
        {
            "types.example.test": lambda request: httpx.Response(
                200,
                headers={"content-type": "Text/HTML; charset=UTF-8"},
                text="<p>x</p>",
            )
        }
    )

    retrieved = await _fetch(
        "https://types.example.test/",
        site,
        FakeResolver({"types.example.test": [PUBLIC_IPV4]}),
    )

    assert retrieved.content_type == "text/html"


async def test_text_is_decoded_with_declared_charset() -> None:
    site = FakeSite(
        {
            "latin.example.test": lambda request: httpx.Response(
                200,
                headers={"content-type": "text/plain; charset=ISO-8859-1"},
                content="café".encode("latin-1"),
            )
        }
    )

    retrieved = await _fetch(
        "https://latin.example.test/",
        site,
        FakeResolver({"latin.example.test": [PUBLIC_IPV4]}),
    )

    assert retrieved.text == "café"


async def test_text_without_declared_charset_is_utf8_with_replacement() -> None:
    site = FakeSite(
        {
            "bytes.example.test": lambda request: httpx.Response(
                200,
                headers={"content-type": RESPONSE_TEXT_TYPE},
                content=b"ok \xff end",
            )
        }
    )

    retrieved = await _fetch(
        "https://bytes.example.test/",
        site,
        FakeResolver({"bytes.example.test": [PUBLIC_IPV4]}),
    )

    assert retrieved.text == "ok � end"
