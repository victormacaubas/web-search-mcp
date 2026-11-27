from __future__ import annotations

import asyncio
import ssl

import httpx
import trustme


async def test_request_to_ip_literal_sends_host_name_as_host_header_and_sni() -> None:
    seen: dict[str, str | None] = {"sni": None, "host_header": None}

    ca = trustme.CA()
    cert = ca.issue_cert("example.test")

    server_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    cert.configure_cert(server_context)

    def record_server_name(
        _sock: ssl.SSLObject, server_name: str | None, _context: ssl.SSLContext
    ) -> None:
        seen["sni"] = server_name

    server_context.sni_callback = record_server_name

    async def answer(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        head = await reader.readuntil(b"\r\n\r\n")
        for line in head.decode("latin-1").split("\r\n"):
            name, _, value = line.partition(":")
            if name.lower() == "host":
                seen["host_header"] = value.strip()
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(answer, "127.0.0.1", 0, ssl=server_context)
    port = server.sockets[0].getsockname()[1]
    client_context = ssl.create_default_context()
    ca.configure_trust(client_context)

    async with server, httpx.AsyncClient(verify=client_context) as client:
        response = await client.get(
            f"https://127.0.0.1:{port}/",
            headers={"Host": "example.test"},
            extensions={"sni_hostname": "example.test"},
        )

    assert response.status_code == 200
    assert seen["sni"] == "example.test"
    assert seen["host_header"] == "example.test"
