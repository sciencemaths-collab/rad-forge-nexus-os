import asyncio
import json
from pathlib import Path

import pytest

from nexus_os.local_openai_adapter import TransportError
from nexus_os.loopback_http_transport import LoopbackHTTPTransport
from nexus_os.sandbox import WorkspaceSandbox


class Response:
    def __init__(self, body: bytes, *, status: int = 200, headers=None):  # type: ignore[no-untyped-def]
        self.status = status
        self.body = body
        self.headers = headers or {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }

    def getheader(self, name, default=None):  # type: ignore[no-untyped-def]
        return self.headers.get(name, default)

    def read(self, amount=None):  # type: ignore[no-untyped-def]
        return self.body if amount is None else self.body[:amount]


class Connection:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.requests = []
        self.closed = False

    def request(self, method, url, body=None, headers=None):  # type: ignore[no-untyped-def]
        self.requests.append((method, url, body, dict(headers or {})))

    def getresponse(self):  # type: ignore[no-untyped-def]
        return self.response

    def close(self) -> None:
        self.closed = True


def subject(tmp_path: Path, connection: Connection, *, hosts=("127.0.0.1",)):
    calls = []

    def factory(scheme, host, port, timeout):  # type: ignore[no-untyped-def]
        calls.append((scheme, host, port, timeout))
        return connection

    sandbox = WorkspaceSandbox(tmp_path, network_hosts=hosts)
    return LoopbackHTTPTransport(sandbox=sandbox, connection_factory=factory), calls


def completion_body() -> bytes:
    return json.dumps({"id": "local-1", "object": "chat.completion", "choices": []}).encode()


def test_completion_posts_canonical_json_with_optional_bearer_and_closes(tmp_path: Path) -> None:
    connection = Connection(Response(completion_body()))
    transport, calls = subject(tmp_path, connection)
    result = asyncio.run(
        transport.create_chat_completion(
            "http://127.0.0.1:11434/v1", {"model": "tiny", "stream": False}, "key", 12
        )
    )
    assert result["id"] == "local-1"
    assert calls == [("http", "127.0.0.1", 11434, 12)]
    method, path, body, headers = connection.requests[0]
    assert (method, path) == ("POST", "/v1/chat/completions")
    assert body == b'{"model":"tiny","stream":false}'
    assert headers["Authorization"] == "Bearer key"
    assert connection.closed


def test_health_uses_models_endpoint_and_returns_boolean(tmp_path: Path) -> None:
    connection = Connection(Response(b"{}"))
    transport, _ = subject(tmp_path, connection)
    assert asyncio.run(transport.health("http://127.0.0.1:11434/v1", None, 5))
    assert connection.requests[0][0:2] == ("GET", "/v1/models")

    unavailable = Connection(Response(b"down", status=503, headers={"Content-Type": "text/plain"}))
    transport, _ = subject(tmp_path, unavailable)
    assert not asyncio.run(transport.health("http://127.0.0.1:11434/v1", None, 5))


def test_localhost_is_pinned_to_ipv4_loopback(tmp_path: Path) -> None:
    connection = Connection(Response(b"{}"))
    transport, calls = subject(tmp_path, connection)
    assert asyncio.run(transport.health("http://localhost:1234/v1", None, 5))
    assert calls[0][1] == "127.0.0.1"


def test_model_discovery_is_bounded_sorted_and_unique(tmp_path: Path) -> None:
    body = json.dumps({"data": [{"id": "model-b"}, {"id": "model-a"}]}).encode()
    transport, _ = subject(tmp_path, Connection(Response(body)))
    assert asyncio.run(transport.list_models("http://127.0.0.1:11434/v1", None, 5)) == (
        "model-a",
        "model-b",
    )

    duplicate = json.dumps({"data": [{"id": "same"}, {"id": "same"}]}).encode()
    transport, _ = subject(tmp_path, Connection(Response(duplicate)))
    with pytest.raises(TransportError, match="duplicates"):
        asyncio.run(transport.list_models("http://127.0.0.1:11434/v1", None, 5))


def test_non_success_completion_and_malformed_json_are_safe(tmp_path: Path) -> None:
    for response, message in (
        (Response(b'{"error":"raw secret"}', status=500), "non-success"),
        (Response(b'{"x":1,"x":2}'), "duplicate"),
        (Response(b"not-json"), "UTF-8 JSON"),
    ):
        transport, _ = subject(tmp_path, Connection(response))
        with pytest.raises(TransportError, match=message) as error:
            asyncio.run(
                transport.create_chat_completion("http://127.0.0.1:1/v1", {"x": 1}, None, 5)
            )
        assert "raw secret" not in str(error.value)
