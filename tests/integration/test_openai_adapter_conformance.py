import asyncio
from collections.abc import Mapping
from typing import Any

from nexus_os.conformance import ConformanceHarness, ConformanceStatus
from nexus_os.openai_adapter import OpenAIAdapter
from nexus_os.secrets import SecretResolver


class ConformanceTransport:
    def __init__(self) -> None:
        self.responses: dict[str, str] = {}

    async def health(self, api_key: str) -> bool:
        return True

    async def create(self, request: Mapping[str, object], api_key: str) -> Mapping[str, Any]:
        task_id = str(request["metadata"]["nexus_task_id"])  # type: ignore[index]
        response_id = "resp_" + task_id.replace("-", "_")
        status = "in_progress" if task_id.endswith(("cancel", "resume")) else "completed"
        self.responses[response_id] = status
        response: dict[str, Any] = {"id": response_id, "status": status, "usage": {}}
        if status == "completed":
            response["output_text"] = "done"
        return response

    async def retrieve(self, response_id: str, api_key: str) -> Mapping[str, Any]:
        return {"id": response_id, "status": self.responses[response_id], "usage": {}}

    async def cancel_response(self, response_id: str, api_key: str) -> Mapping[str, Any]:
        self.responses[response_id] = "cancelled"
        return {"id": response_id, "status": "cancelled", "usage": {}}


def test_openai_adapter_passes_normalized_harness_with_fake_transport() -> None:
    def factory() -> OpenAIAdapter:
        return OpenAIAdapter(
            model="gpt-5.6",
            credential="env:OPENAI_API_KEY",
            resolver=SecretResolver(environment={"OPENAI_API_KEY": "fixture-only"}),
            transport=ConformanceTransport(),
        )

    report = asyncio.run(ConformanceHarness().run(factory))
    assert report.status is ConformanceStatus.PASSED
    assert report.level.value == "mock_verified"
