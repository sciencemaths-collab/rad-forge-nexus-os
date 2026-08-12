import asyncio
import io
from collections.abc import Mapping
from typing import Any

from nexus_os.cli import ExitCode, run_cli
from nexus_os.control_api import ApiContext, ApiRequest, ControlApplication, MemoryControlService
from nexus_os.domain import TraceId


class ApplicationClient:
    def __init__(self, application: ControlApplication) -> None:
        self.application = application
        self.counter = 0

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[int, Mapping[str, Any] | list[Any], Mapping[str, str]]:
        self.counter += 1
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        response = await self.application.handle(
            ApiRequest(method, path, headers, body, f"cli-{self.counter}"),
            ApiContext(
                "cli",
                frozenset({"api:read", "api:write"}),
                TraceId("9" * 32),
            ),
        )
        return response.status, response.body, response.headers


def test_cli_executes_create_and_get_through_control_application() -> None:
    client = ApplicationClient(ControlApplication(MemoryControlService()))
    output = io.StringIO()
    code = asyncio.run(
        run_cli(
            [
                "runs",
                "create",
                "--project-id",
                "project-1",
                "--idempotency-key",
                "1234567890abcdef",
            ],
            client,
            stdout=output,
            stderr=io.StringIO(),
        )
    )
    assert code == ExitCode.SUCCESS
    assert '"state":"SPECIFYING"' in output.getvalue()
