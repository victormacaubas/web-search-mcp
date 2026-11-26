"""Retrieval of one web page over HTTP with an address check on every hop."""

import asyncio
import ipaddress
from importlib.metadata import version
from urllib.parse import urljoin, urlsplit

import httpx

from web_search_mcp.models import Retrieved
from web_search_mcp.netguard import (
    CheckedTarget,
    GuardError,
    Resolver,
    check_url,
    default_resolver,
)

USER_AGENT = f"web-search-mcp/{version('web-search-mcp')}"
ACCEPT = "text/markdown, text/html;q=0.9, application/xhtml+xml;q=0.8, */*;q=0.5"

BYTES_PER_MB = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_BYTES = 5 * BYTES_PER_MB
CONNECT_TIMEOUT_SECONDS = 10.0
MAX_REDIRECTS = 5

_LIMIT_HEADERS_STATUSES = frozenset({403, 429})
_LIMIT_HEADERS = ("Retry-After", "X-RateLimit-Remaining", "X-RateLimit-Reset")


class FetchError(Exception):
    """A page could not be retrieved."""


async def retrieve(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    resolver: Resolver = default_resolver,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Retrieved:
    """Retrieve a page, checking the address of the URL and of each redirect.

    Args:
        url: Absolute http or https URL.
        client: HTTP client to use. When None, a client with a 10 second connect
            timeout is created for this call.
        resolver: Host name resolver for the address check.
        timeout: Seconds allowed for the whole retrieval, redirects included.
        max_bytes: Largest decoded body to read.

    Raises:
        FetchError: The URL is refused, the request fails, the status is not 2xx,
            or a limit on redirects, size, or time is passed. The message names
            URLs in their host-name form.
    """
    try:
        async with asyncio.timeout(timeout):
            if client is not None:
                return await _follow_redirects(url, client, resolver, max_bytes)
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT_SECONDS)
            ) as owned:
                return await _follow_redirects(url, owned, resolver, max_bytes)
    except TimeoutError:
        raise FetchError(
            f"Retrieval of {url} passed the time limit of {timeout:g} seconds."
        ) from None


async def _follow_redirects(
    url: str, client: httpx.AsyncClient, resolver: Resolver, max_bytes: int
) -> Retrieved:
    current = url
    for redirects in range(MAX_REDIRECTS + 1):
        try:
            target = await check_url(current, resolver)
        except GuardError as exc:
            raise FetchError(str(exc)) from exc
        response = await _send(client, target)
        try:
            if response.is_redirect:
                if redirects == MAX_REDIRECTS:
                    raise FetchError(
                        f"Stopped at the redirect limit of {MAX_REDIRECTS} "
                        f"redirects for {url}."
                    )
                current = urljoin(current, response.headers["location"])
                continue
            return await _read(url, current, response, max_bytes)
        finally:
            await response.aclose()
    raise AssertionError("unreachable: the last hop returns or raises")


async def _send(client: httpx.AsyncClient, target: CheckedTarget) -> httpx.Response:
    extensions = {} if _is_ip_literal(target.host) else {"sni_hostname": target.host}
    try:
        request = client.build_request(
            "GET",
            target.connect_url,
            headers={
                "Host": urlsplit(target.url).netloc,
                "Accept": ACCEPT,
                "User-Agent": USER_AGENT,
            },
            extensions=extensions,
        )
        return await client.send(request, stream=True, follow_redirects=False)
    except httpx.InvalidURL as exc:
        raise FetchError(f"Invalid URL {target.url}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise FetchError(
            f"Network failure for {target.url}: {type(exc).__name__}: {exc}"
        ) from exc


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


async def _read(
    requested_url: str, final_url: str, response: httpx.Response, max_bytes: int
) -> Retrieved:
    if not response.is_success:
        raise FetchError(_status_message(response, final_url))
    body = bytearray()
    try:
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise FetchError(
                    f"The body of {final_url} is larger than "
                    f"{max_bytes / BYTES_PER_MB:g} MB, so the read was stopped."
                )
    except httpx.HTTPError as exc:
        raise FetchError(
            f"Network failure while reading {final_url}: {type(exc).__name__}: {exc}"
        ) from exc
    media_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    return Retrieved(
        requested_url=requested_url,
        final_url=final_url,
        status=response.status_code,
        content_type=media_type,
        text=_decode(bytes(body), response.charset_encoding),
    )


def _status_message(response: httpx.Response, final_url: str) -> str:
    message = f"Request failed with status {response.status_code} for {final_url}."
    if response.status_code in _LIMIT_HEADERS_STATUSES:
        present = [
            f"{name}: {response.headers[name]}"
            for name in _LIMIT_HEADERS
            if name in response.headers
        ]
        if present:
            message += " " + "; ".join(present) + "."
    return message


def _decode(body: bytes, charset: str | None) -> str:
    try:
        return body.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
