"""Address guard that refuses URLs which are not public http(s) addresses."""

import asyncio
import dataclasses
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

_NAT64_WELL_KNOWN = ipaddress.IPv6Network("64:ff9b::/96")
_NAT64_LOCAL_USE = ipaddress.IPv6Network("64:ff9b:1::/48")
_SITE_LOCAL = ipaddress.IPv6Network("fec0::/10")
IPV6_VERSION = 6
_IPV4_BITS = 32
_IPV4_MASK = (1 << _IPV4_BITS) - 1

Resolver = Callable[[str], Awaitable[list[str]]]


class GuardError(Exception):
    """A URL was refused: scheme, user information, or an address that is not public."""


class NameNotResolvedError(GuardError):
    """The host name did not resolve to any address."""


@dataclasses.dataclass(frozen=True)
class CheckedTarget:
    """A URL whose host passed the check, with the address to connect to."""

    url: str
    host: str
    address: str
    connect_url: str


async def default_resolver(host: str) -> list[str]:
    """Resolve a host name to its IP address strings with the event loop resolver."""
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, None, type=socket.SOCK_STREAM
    )
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def _unwrapped(address: IPAddress) -> IPAddress | None:
    """Return the IPv4 address embedded in an IPv6 transition address, if any."""
    if not isinstance(address, ipaddress.IPv6Address):
        return None
    if address.ipv4_mapped is not None:
        return address.ipv4_mapped
    if address.sixtofour is not None:
        return address.sixtofour
    if address in _NAT64_WELL_KNOWN or address in _NAT64_LOCAL_USE:
        return ipaddress.IPv4Address(int(address) & _IPV4_MASK)
    return None


def _is_public(address: IPAddress) -> bool:
    if not address.is_global or address.is_multicast:
        return False
    return not (isinstance(address, ipaddress.IPv6Address) and address in _SITE_LOCAL)


def _all_forms_public(address: IPAddress) -> bool:
    if not _is_public(address):
        return False
    embedded = _unwrapped(address)
    return embedded is None or _is_public(embedded)


def _parse_ip(text: str) -> IPAddress | None:
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def _connect_url(url: str, address: IPAddress, port: int | None) -> str:
    parts = urlsplit(url)
    host = f"[{address}]" if address.version == IPV6_VERSION else str(address)
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit(parts._replace(netloc=netloc))


async def check_url(url: str, resolver: Resolver = default_resolver) -> CheckedTarget:
    """Check that a URL points only to public addresses.

    The host is resolved one time. Every address it resolves to must be public,
    so a name with one public and one private address is refused.

    Args:
        url: Absolute http or https URL without user information.
        resolver: Maps a host name to IP address strings. It raises
            `socket.gaierror` for an unknown name.

    Returns:
        The checked address and a URL that uses it, so the caller connects to the
        address that was checked and does not resolve the name again.

    Raises:
        GuardError: The scheme, the user information, or an address is refused.
        NameNotResolvedError: The host name did not resolve.
    """
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise GuardError(f"Refused {url}: only http and https URLs are allowed.")
    if "@" in parts.netloc:
        raise GuardError("Refused: URLs with user information are not allowed.")
    try:
        port = parts.port
    except ValueError as exc:
        raise GuardError(f"Refused {url}: the port is not valid.") from exc
    host = parts.hostname
    if not host:
        raise GuardError(f"Refused {url}: the URL has no host.")

    literal = _parse_ip(host)
    if literal is not None:
        addresses = [literal]
    else:
        try:
            resolved = await resolver(host)
        except socket.gaierror as exc:
            raise NameNotResolvedError(f"Host name not resolved: {host}") from exc
        addresses = [parsed for text in resolved if (parsed := _parse_ip(text))]
        if not addresses:
            raise NameNotResolvedError(f"Host name not resolved: {host}")

    if not all(_all_forms_public(address) for address in addresses):
        raise GuardError(f"Refused {host}: it is not a public address.")

    chosen = addresses[0]
    return CheckedTarget(
        url=url,
        host=host,
        address=str(chosen),
        connect_url=_connect_url(url, chosen, port),
    )
