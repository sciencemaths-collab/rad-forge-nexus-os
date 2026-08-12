import asyncio
from collections.abc import Mapping
from typing import Any

from nexus_os.anthropic_adapter import AnthropicAdapter
from nexus_os.conformance import ConformanceHarness, ConformanceStatus
from nexus_os.secrets import SecretResolver


class ConformanceTransport:
    async def health(self, api_key: str) -> bool:
        return True

    async def create(self, request: Mapping[str, object], api_key: str) -> Mapping[str, Any]:
        task_id = str(request["metadata"]["user_id"])  # type: ignore[index]
        return {
            "id": "msg_" + task_id.replace("-", "_"),
            "type": "message",
            "role": "assistant",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "done"}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }


def test_anthropic_adapter_passes_normalized_harness_with_fake_transport() -> None:
    def factory() -> AnthropicAdapter:
        return AnthropicAdapter(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            credential="env:ANTHROPIC_API_KEY",
            resolver=SecretResolver(environment={"ANTHROPIC_API_KEY": "fixture-only"}),
            transport=ConformanceTransport(),
        )

    report = asyncio.run(ConformanceHarness().run(factory))
    assert report.status is ConformanceStatus.PASSED
    assert report.level.value == "mock_verified"
