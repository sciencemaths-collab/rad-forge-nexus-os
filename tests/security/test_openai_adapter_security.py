import asyncio
import inspect

import pytest

import nexus_os.openai_adapter as openai_adapter
from nexus_os.openai_adapter import OpenAIAdapter, TransportError
from nexus_os.secrets import SecretResolver


class FailingTransport:
    async def health(self, api_key: str) -> bool:
        raise TransportError(f"upstream failed {api_key}")


def test_transport_failure_does_not_leak_resolved_secret() -> None:
    subject = OpenAIAdapter(
        model="gpt-5.6",
        credential="env:OPENAI_API_KEY",
        resolver=SecretResolver(environment={"OPENAI_API_KEY": "OPENAI_SECRET_CANARY"}),
        transport=FailingTransport(),  # type: ignore[arg-type]
    )
    with pytest.raises(Exception) as caught:
        asyncio.run(subject.healthcheck())
    assert "OPENAI_SECRET_CANARY" not in str(caught.value)


def test_adapter_has_no_vendor_sdk_or_ambient_environment_access() -> None:
    source = inspect.getsource(openai_adapter)
    assert "import openai" not in source
    assert "os.environ" not in source
    assert "requests" not in source


def test_literal_credential_and_unsafe_model_are_rejected() -> None:
    resolver = SecretResolver(environment={})
    for credential in ("sk-literal", "OPENAI_API_KEY"):
        with pytest.raises(ValueError):
            OpenAIAdapter(
                model="gpt-5.6",
                credential=credential,
                resolver=resolver,
                transport=FailingTransport(),  # type: ignore[arg-type]
            )
    with pytest.raises(ValueError):
        OpenAIAdapter(
            model="../../model",
            credential="env:OPENAI_API_KEY",
            resolver=resolver,
            transport=FailingTransport(),  # type: ignore[arg-type]
        )
