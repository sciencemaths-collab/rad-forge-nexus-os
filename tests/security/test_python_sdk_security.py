import asyncio

import pytest

from nexus_os.python_sdk import ApiError, NexusClient, SdkValidationError


class HostileTransport:
    async def send(self, method, path, headers, body):  # type: ignore[no-untyped-def]
        return 500, {"code": "bad", "message": "SECRET_CANARY", "retryable": False}, {}


def test_invalid_identifiers_and_keys_fail_before_transport() -> None:
    client = NexusClient(HostileTransport())
    cases = (
        client.get_run("not-a-uuid"),
        client.create_run("p", idempotency_key="short"),
        client.create_run("x" * 257, idempotency_key="1234567890abcdef"),
    )
    for operation in cases:
        with pytest.raises(SdkValidationError):
            asyncio.run(operation)


def test_malformed_error_does_not_echo_untrusted_message() -> None:
    with pytest.raises(ApiError) as caught:
        asyncio.run(NexusClient(HostileTransport()).list_providers())
    assert "SECRET_CANARY" not in str(caught.value)


def test_malformed_success_and_trace_are_rejected() -> None:
    class Bad:
        async def send(self, method, path, headers, body):  # type: ignore[no-untyped-def]
            return 200, {"unexpected": True}, {"X-Trace-Id": "bad"}

    with pytest.raises(SdkValidationError):
        asyncio.run(NexusClient(Bad()).get_run("00000000-0000-4000-8000-000000000001"))
