import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from nexus_os.control_api import ApiContext, ApiRequest, ControlApplication
from nexus_os.domain import TraceId


class RecordingService:
    def __init__(self) -> None:
        self.operations: list[str] = []

    async def invoke(
        self,
        operation: str,
        path_values: Mapping[str, str],
        body: Mapping[str, Any] | None,
        context: ApiContext,
    ) -> tuple[int, Mapping[str, Any] | list[Any]]:
        self.operations.append(operation)
        return 418, {"operation": operation}


def test_every_frozen_openapi_operation_is_represented_by_dispatcher() -> None:
    contract = yaml.safe_load(Path("contracts/openapi.yaml").read_text(encoding="utf-8"))
    expected = {
        operation["operationId"]
        for methods in contract["paths"].values()
        for operation in methods.values()
    }
    service = RecordingService()
    app = ControlApplication(service)
    context = ApiContext(
        "integration",
        frozenset({"api:read", "api:write", "approvals:decide"}),
        TraceId("7" * 32),
    )
    identifier = "00000000-0000-4000-8000-000000000001"
    cases = (
        ("POST", "/v1/projects", {}),
        ("GET", "/v1/projects/project-1", None),
        ("POST", "/v1/projects/project-1/plan", None),
        ("POST", "/v1/runs", {"project_id": "project-1"}),
        ("GET", f"/v1/runs/{identifier}", None),
        ("POST", f"/v1/runs/{identifier}/cancel", None),
        ("POST", f"/v1/runs/{identifier}/resume", None),
        ("GET", f"/v1/runs/{identifier}/evidence", None),
        ("GET", f"/v1/approvals/{identifier}", None),
        ("POST", f"/v1/approvals/{identifier}/decision", {"decision": "APPROVED"}),
        ("GET", "/v1/providers", None),
        ("GET", "/v1/capabilities", None),
    )
    for index, (method, path, body) in enumerate(cases):
        headers = {"Idempotency-Key": f"1234567890abcdef{index}"} if method == "POST" else {}
        response = asyncio.run(
            app.handle(ApiRequest(method, path, headers, body, f"r-{index}"), context)
        )
        assert response.status == 418

    assert set(service.operations) == expected
