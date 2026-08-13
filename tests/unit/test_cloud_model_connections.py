import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from nexus_os.agent_model_config import AgentModelConfigError, load_agent_model_config
from nexus_os.anthropic_adapter import TransportError as AnthropicTransportError
from nexus_os.cloud_http_transport import AnthropicHTTPTransport, OpenAIHTTPTransport
from nexus_os.openai_adapter import TransportError as OpenAITransportError
from nexus_os.rad_cli import parser, setup_local


class Response:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self.status = status
        self.body = json.dumps(payload).encode()

    def getheader(self, name: str, default: str | None = None) -> str | None:
        if name == "Content-Type":
            return "application/json"
        if name == "Content-Length":
            return str(len(self.body))
        return default

    def read(self, amount: int | None = None) -> bytes:
        return self.body if amount is None else self.body[:amount]


class Connection:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.requests: list[tuple[str, str, bytes | None, Mapping[str, str]]] = []

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: Mapping[str, str] = {},
    ) -> None:
        self.requests.append((method, url, body, headers))

    def getresponse(self) -> Response:
        return self.response

    def close(self) -> None:
        pass


def passwords():
    values = iter(("correct horse battery staple", "correct horse battery staple"))
    return lambda _prompt: next(values)


def test_cloud_setup_writes_exact_redacted_openai_profile(tmp_path: Path) -> None:
    root = tmp_path / "openai"
    values = parser().parse_args(
        [
            "setup",
            "--config-dir",
            str(root),
            "--provider",
            "openai",
            "--model",
            "gpt-5",
            "--credential-ref",
            "env:OPENAI_API_KEY",
        ]
    )
    result = setup_local(values, password_reader=passwords())
    profile = load_agent_model_config(root / "models.yaml").profiles["local_default"]
    assert result["provider"] == "openai"
    assert profile.base_url == "https://api.openai.com/v1"
    assert profile.public_dict()["credential"] == "<redacted-reference>"


@pytest.mark.parametrize(
    ("provider", "url"),
    [
        ("openai", "https://other.example/v1"),
        ("anthropic", "https://api.openai.com/v1"),
    ],
)
def test_cloud_profiles_reject_endpoint_override(tmp_path: Path, provider: str, url: str) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        "schema_version: '1.0'\nselected: cloud\nprofiles:\n  cloud:\n"
        f"    type: {provider}\n    base_url: {url}\n    model: model-1\n"
        "    credential: env:CLOUD_KEY\n",
        encoding="utf-8",
    )
    with pytest.raises(AgentModelConfigError, match="endpoint"):
        load_agent_model_config(path)


def test_openai_transport_uses_only_official_host_and_bearer_header() -> None:
    connection = Connection(Response({"data": [{"id": "gpt-5"}]}))
    subject = OpenAIHTTPTransport(connection_factory=lambda host, timeout: connection)
    assert __import__("asyncio").run(subject.list_models("secret-key")) == ("gpt-5",)
    method, path, body, headers = connection.requests[0]
    assert (method, path, body) == ("GET", "/v1/models", None)
    assert headers["Authorization"] == "Bearer secret-key"
    assert "secret-key" not in repr(subject)


def test_anthropic_transport_sets_version_and_rejects_error_body() -> None:
    connection = Connection(Response({"data": [{"id": "claude-sonnet-4"}]}))
    subject = AnthropicHTTPTransport(connection_factory=lambda host, timeout: connection)
    assert __import__("asyncio").run(subject.list_models("secret-key")) == (
        "claude-sonnet-4",
    )
    headers = connection.requests[0][3]
    assert headers["x-api-key"] == "secret-key"
    assert headers["anthropic-version"] == "2023-06-01"

    failed = AnthropicHTTPTransport(
        connection_factory=lambda host, timeout: Connection(
            Response({"error": {"message": "sensitive"}}, status=401)
        )
    )
    with pytest.raises(AnthropicTransportError, match="non-success"):
        __import__("asyncio").run(failed.list_models("secret-key"))


def test_cloud_transports_reject_header_injection() -> None:
    connection = Connection(Response({"data": []}))
    openai = OpenAIHTTPTransport(connection_factory=lambda host, timeout: connection)
    with pytest.raises(OpenAITransportError, match="credential"):
        __import__("asyncio").run(openai.list_models("secret\r\nInjected: yes"))
