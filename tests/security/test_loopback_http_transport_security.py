import asyncio
from pathlib import Path

import pytest

from nexus_os.local_openai_adapter import TransportError
from nexus_os.loopback_http_transport import LoopbackHTTPTransport
from nexus_os.sandbox import WorkspaceSandbox
from tests.unit.test_loopback_http_transport import Connection, Response, subject


def test_network_is_denied_without_exact_pinned_host_authorization(tmp_path: Path) -> None:
    connection = Connection(Response(b"{}"))
    transport = LoopbackHTTPTransport(
        sandbox=WorkspaceSandbox(tmp_path),
        connection_factory=lambda scheme, host, port, timeout: connection,
    )
    assert not asyncio.run(transport.health("http://127.0.0.1:11434/v1", None, 5))
    with pytest.raises(TransportError, match="not authorized"):
        asyncio.run(
            transport.create_chat_completion("http://127.0.0.1:11434/v1", {"x": 1}, None, 5)
        )
    assert not connection.requests


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.com:11434/v1",
        "http://0.0.0.0:11434/v1",
        "http://127.0.0.1:11434/v2",
        "http://user:pass@127.0.0.1:11434/v1",
        "http://127.0.0.1:11434/v1?redirect=1",
    ],
)
def test_remote_ambiguous_and_credential_endpoints_are_rejected(
    tmp_path: Path, endpoint: str
) -> None:
    transport, calls = subject(tmp_path, Connection(Response(b"{}")))
    with pytest.raises(TransportError, match="loopback"):
        asyncio.run(transport.create_chat_completion(endpoint, {"x": 1}, None, 5))
    assert not calls


def test_oversized_declared_and_streamed_responses_are_rejected(tmp_path: Path) -> None:
    declared = Connection(
        Response(b"{}", headers={"Content-Type": "application/json", "Content-Length": "2000001"})
    )
    streamed = Connection(Response(b"x" * 2_000_001, headers={"Content-Type": "application/json"}))
    for connection in (declared, streamed):
        transport, _ = subject(tmp_path, connection)
        with pytest.raises(TransportError, match="oversized"):
            asyncio.run(
                transport.create_chat_completion("http://127.0.0.1:11434/v1", {"x": 1}, None, 5)
            )


def test_header_injection_credential_and_non_json_success_are_rejected(tmp_path: Path) -> None:
    connection = Connection(
        Response(b"hello", headers={"Content-Type": "text/plain", "Content-Length": "5"})
    )
    transport, _ = subject(tmp_path, connection)
    with pytest.raises(TransportError, match="credential"):
        asyncio.run(
            transport.create_chat_completion(
                "http://127.0.0.1:11434/v1", {"x": 1}, "bad\r\nheader", 5
            )
        )
    with pytest.raises(TransportError, match="content type"):
        asyncio.run(
            transport.create_chat_completion("http://127.0.0.1:11434/v1", {"x": 1}, None, 5)
        )
