from __future__ import annotations

import pytest

from tests.fetch_fakes import PUBLIC_IPV4, PUBLIC_IPV6, FakeResolver
from web_search_mcp.netguard import GuardError, NameNotResolvedError, check_url

NAMES = {
    "localhost": ["127.0.0.1"],
    "private.example.test": ["10.0.0.5"],
    "mixed.example.test": [PUBLIC_IPV4, "10.0.0.5"],
    "public4.example.test": [PUBLIC_IPV4],
    "public6.example.test": [PUBLIC_IPV6],
    "mapped-private.example.test": ["::ffff:10.0.0.5"],
}


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("http://localhost:8080/", id="localhost-name"),
        pytest.param("http://127.0.0.1/", id="ipv4-loopback"),
        pytest.param("http://10.0.0.5/", id="ipv4-private-10"),
        pytest.param("http://192.168.1.1/", id="ipv4-private-192"),
        pytest.param("http://169.254.169.254/latest/meta-data/", id="cloud-metadata"),
        pytest.param("http://100.64.0.1/", id="ipv4-shared"),
        pytest.param("http://0.0.0.0/", id="ipv4-unspecified"),
        pytest.param("http://224.0.0.1/", id="ipv4-multicast"),
        pytest.param("http://[::1]/", id="ipv6-loopback"),
        pytest.param("http://[::ffff:127.0.0.1]/", id="ipv4-mapped-loopback"),
        pytest.param("http://[::127.0.0.1]/", id="ipv4-compatible-loopback"),
        pytest.param("http://[::10.0.0.1]/", id="ipv4-compatible-private"),
        pytest.param(
            "http://[::169.254.169.254]/latest/meta-data/",
            id="ipv4-compatible-metadata",
        ),
        pytest.param("http://[::ffff:0:127.0.0.1]/", id="siit-translated-loopback"),
        pytest.param(
            "http://[::ffff:0:169.254.169.254]/", id="siit-translated-metadata"
        ),
        pytest.param("http://[200::1]/", id="ipv6-ietf-reserved"),
        pytest.param("http://[64:ff9b::a9fe:a9fe]/", id="nat64-metadata"),
        pytest.param("http://[64:ff9b:1::a00:5]/", id="nat64-48-embedded-private"),
        pytest.param("http://[2002:7f00:1::]/", id="6to4-embedded-loopback"),
        pytest.param("http://[2002:a9fe:a9fe::]/", id="6to4-embedded-metadata"),
        pytest.param("http://[ff02::1]/", id="ipv6-multicast"),
        pytest.param("http://[fec0::1]/", id="ipv6-site-local"),
        pytest.param("http://[fe80::1]/", id="ipv6-link-local"),
        pytest.param("http://private.example.test/", id="name-resolving-to-private"),
        pytest.param("http://mixed.example.test/", id="name-with-public-and-private"),
        pytest.param(
            "http://mapped-private.example.test/", id="name-resolving-to-mapped-private"
        ),
    ],
)
async def test_address_that_is_not_public_is_refused(url: str) -> None:
    with pytest.raises(GuardError, match="not a public address"):
        await check_url(url, resolver=FakeResolver(NAMES))


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("file:///etc/hosts", id="file-scheme"),
        pytest.param("ftp://public4.example.test/file.txt", id="ftp-scheme"),
        pytest.param(
            "https://user:secret@public4.example.test/", id="user-and-password"
        ),
        pytest.param("http://user@public4.example.test/", id="user-name-only"),
    ],
)
async def test_unsupported_scheme_or_user_information_is_refused_without_resolving(
    url: str,
) -> None:
    resolver = FakeResolver(NAMES)
    with pytest.raises(GuardError):
        await check_url(url, resolver=resolver)
    assert resolver.calls == []


@pytest.mark.parametrize(
    ("url", "host", "address", "connect_url"),
    [
        pytest.param(
            "https://public4.example.test/docs?x=1",
            "public4.example.test",
            PUBLIC_IPV4,
            "https://93.184.216.34/docs?x=1",
            id="name-with-public-ipv4",
        ),
        pytest.param(
            "https://public6.example.test:8443/docs",
            "public6.example.test",
            PUBLIC_IPV6,
            "https://[2606:2800:220:1:248:1893:25c8:1946]:8443/docs",
            id="name-with-public-ipv6-and-port",
        ),
    ],
)
async def test_name_with_public_address_is_accepted_and_connect_url_uses_that_address(
    url: str, host: str, address: str, connect_url: str
) -> None:
    target = await check_url(url, resolver=FakeResolver(NAMES))

    assert target.url == url
    assert target.host == host
    assert target.address == address
    assert target.connect_url == connect_url
    assert target.sni_hostname == host


@pytest.mark.parametrize(
    ("url", "address", "connect_url"),
    [
        pytest.param(
            "http://93.184.216.34/",
            PUBLIC_IPV4,
            "http://93.184.216.34/",
            id="public-ipv4-literal",
        ),
        pytest.param(
            "http://[2606:2800:220:1:248:1893:25c8:1946]:8080/a",
            PUBLIC_IPV6,
            "http://[2606:2800:220:1:248:1893:25c8:1946]:8080/a",
            id="public-ipv6-literal-with-port",
        ),
    ],
)
async def test_ip_literal_is_used_as_given_without_calling_resolver(
    url: str, address: str, connect_url: str
) -> None:
    resolver = FakeResolver(NAMES)
    target = await check_url(url, resolver=resolver)

    assert resolver.calls == []
    assert target.address == address
    assert target.connect_url == connect_url
    assert target.sni_hostname is None


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("http://[::ffff:8.8.8.8]/", id="ipv4-mapped-public"),
        pytest.param("http://[64:ff9b::8.8.8.8]/", id="nat64-well-known-public"),
    ],
)
async def test_transition_ipv6_literal_with_public_ipv4_is_accepted(url: str) -> None:
    resolver = FakeResolver(NAMES)

    target = await check_url(url, resolver=resolver)

    assert resolver.calls == []
    assert target.sni_hostname is None


async def test_name_that_does_not_resolve_raises_not_resolved_error() -> None:
    with pytest.raises(NameNotResolvedError, match="not resolved"):
        await check_url("https://nowhere.example.test/", resolver=FakeResolver({}))
