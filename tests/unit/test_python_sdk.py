import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from nexus_os.python_sdk import ApiError, NexusClient, Run


class Transport:
    def __init__(self, status: int = 200, body: Mapping[str, Any] | list[Any] | None = None):
        self.status = status
        self.body = body if body is not None else []
        self.calls: list[tuple[str, str, Mapping[str, str], object]] = []

    async def send(self, method, path, headers, body):  # type: ignore[no-untyped-def]
        self.calls.append((method, path, headers, body))
        return self.status, self.body, {"X-Trace-Id": "a" * 32}


def test_create_run_returns_typed_model_and_preserves_headers() -> None:
    body = {
        "run_id": "00000000-0000-4000-8000-000000000001",
        "project_id": "project-1",
        "state": "SPECIFYING",
    }
    transport = Transport(202, body)
    client = NexusClient(transport)
    run = asyncio.run(
        client.create_run("project-1", idempotency_key="1234567890abcdef", request_id="request-1")
    )
    assert run == Run(**body)
    method, path, headers, request_body = transport.calls[0]
    assert (method, path, request_body) == ("POST", "/v1/runs", {"project_id": "project-1"})
    assert headers["Idempotency-Key"] == "1234567890abcdef"
    assert headers["X-Request-Id"] == "request-1"


def test_all_read_collections_and_get_run_are_typed() -> None:
    identifier = "00000000-0000-4000-8000-000000000001"
    transport = Transport(200, [])
    client = NexusClient(transport)
    assert asyncio.run(client.list_providers()) == ()
    assert asyncio.run(client.list_capabilities()) == ()
    assert asyncio.run(client.list_evidence(identifier)) == ()

    transport.body = {"run_id": identifier, "project_id": "p", "state": "RUNNING"}
    assert asyncio.run(client.get_run(identifier)).state == "RUNNING"


def test_api_error_is_structured_and_safe() -> None:
    transport = Transport(
        403,
        {"code": "forbidden", "message": "Denied", "request_id": "r1", "retryable": False},
    )
    with pytest.raises(ApiError) as caught:
        asyncio.run(NexusClient(transport).list_providers())
    assert caught.value.status == 403
    assert caught.value.code == "forbidden"
    assert caught.value.retryable is False
