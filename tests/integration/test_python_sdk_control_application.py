import asyncio
from collections.abc import Mapping
from typing import Any

from nexus_os.control_api import ApiContext, ApiRequest, ControlApplication, MemoryControlService
from nexus_os.domain import TraceId
from nexus_os.python_sdk import NexusClient


class ApplicationTransport:
    def __init__(self) -> None:
        self.application = ControlApplication(MemoryControlService())

    async def send(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any] | list[Any], Mapping[str, str]]:
        response = await self.application.handle(
            ApiRequest(method, path, headers, body, headers["X-Request-Id"]),
            ApiContext(
                "sdk",
                frozenset({"api:read", "api:write"}),
                TraceId("b" * 32),
            ),
        )
        return response.status, response.body, response.headers


def test_sdk_create_then_get_runs_through_control_application() -> None:
    client = NexusClient(ApplicationTransport())
    created = asyncio.run(
        client.create_run("project-1", idempotency_key="1234567890abcdef")
    )
    fetched = asyncio.run(client.get_run(created.run_id))
    assert fetched == created
