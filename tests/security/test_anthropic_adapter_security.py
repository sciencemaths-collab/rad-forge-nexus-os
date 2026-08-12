import asyncio
import inspect

import pytest

import nexus_os.anthropic_adapter as anthropic_adapter
from nexus_os.anthropic_adapter import AnthropicAdapter, TransportError
from nexus_os.secrets import SecretResolver


class FailingTransport:
    async def health(self, api_key: str) -> bool:
        raise TransportError(f"upstream failed {api_key}")


def test_transport_failure_does_not_leak_resolved_secret() -> None:
    subject = AnthropicAdapter(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        credential="env:ANTHROPIC_API_KEY",
        resolver=SecretResolver(environment={"ANTHROPIC_API_KEY": "CLAUDE_SECRET_CANARY"}),
        transport=FailingTransport(),  # type: ignore[arg-type]
    )
    with pytest.raises(Exception) as caught:
        asyncio.run(subject.healthcheck())
    assert "CLAUDE_SECRET_CANARY" not in str(caught.value)


def test_adapter_has_no_vendor_sdk_or_ambient_environment_access() -> None:
    source = inspect.getsource(anthropic_adapter)
    assert "import anthropic" not in source
    assert "os.environ" not in source
    assert "requests" not in source


def test_invalid_configuration_is_rejected() -> None:
    resolver = SecretResolver(environment={})
    for model, tokens, credential in (
        ("../../model", 100, "env:ANTHROPIC_API_KEY"),
        ("claude-model", 0, "env:ANTHROPIC_API_KEY"),
        ("claude-model", 100, "sk-ant-literal"),
    ):
        with pytest.raises(ValueError):
            AnthropicAdapter(
                model=model,
                max_tokens=tokens,
                credential=credential,
                resolver=resolver,
                transport=FailingTransport(),  # type: ignore[arg-type]
            )
