import asyncio
import inspect

import pytest

import nexus_os.local_openai_adapter as local_adapter
from nexus_os.local_openai_adapter import LocalOpenAIAdapter, TransportError
from nexus_os.secrets import SecretResolver


class FailingTransport:
    async def health(self, base_url: str, api_key: str | None, timeout_seconds: int) -> bool:
        raise TransportError(f"local failure {api_key}")


def make(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "local-model",
        "credential": None,
        "resolver": SecretResolver(environment={}),
        "transport": FailingTransport(),
    }
    values.update(overrides)
    return LocalOpenAIAdapter(**values)


def test_adapter_rejects_remote_ambiguous_and_credential_bearing_endpoints() -> None:
    for endpoint in (
        "https://example.com/v1",
        "http://0.0.0.0:11434/v1",
        "http://local.test:11434/v1",
        "http://user:password@127.0.0.1:11434/v1",
        "http://127.0.0.1:11434/v1?token=value",
        "file:///tmp/model",
    ):
        with pytest.raises(ValueError):
            make(base_url=endpoint)


def test_literal_credential_unsafe_model_and_invalid_limits_are_rejected() -> None:
    for overrides in (
        {"credential": "literal-key"},
        {"model": "../../model"},
        {"max_tokens": 0},
        {"temperature": float("nan")},
    ):
        with pytest.raises(ValueError):
            make(**overrides)


def test_transport_failure_does_not_leak_optional_resolved_secret() -> None:
    subject = make(
        credential="env:LOCAL_MODEL_KEY",
        resolver=SecretResolver(environment={"LOCAL_MODEL_KEY": "LOCAL_SECRET_CANARY"}),
    )
    with pytest.raises(Exception) as caught:
        asyncio.run(subject.healthcheck())
    assert "LOCAL_SECRET_CANARY" not in str(caught.value)


def test_adapter_has_no_vendor_sdk_ambient_environment_or_network_client() -> None:
    source = inspect.getsource(local_adapter)
    assert "import openai" not in source
    assert "os.environ" not in source
    assert "requests" not in source
    assert "urllib.request" not in source
