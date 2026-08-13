import asyncio
from collections.abc import Mapping
from typing import Any

from nexus_os.conformance import ConformanceHarness, ConformanceStatus
from nexus_os.local_openai_adapter import LocalOpenAIAdapter
from nexus_os.secrets import SecretResolver


class ConformanceTransport:
    async def health(self, base_url: str, api_key: str | None, timeout_seconds: int) -> bool:
        return True

    async def create_chat_completion(
        self,
        base_url: str,
        request: Mapping[str, object],
        api_key: str | None,
        timeout_seconds: int,
    ) -> Mapping[str, Any]:
        return {
            "id": "chatcmpl-conformance",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "ok"},
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }


def test_local_adapter_passes_normalized_harness_with_fake_transport() -> None:
    def factory() -> LocalOpenAIAdapter:
        return LocalOpenAIAdapter(
            base_url="http://localhost:11434/v1",
            model="local-reference",
            credential=None,
            resolver=SecretResolver(environment={}),
            transport=ConformanceTransport(),
        )

    report = asyncio.run(ConformanceHarness().run(factory))
    assert report.status is ConformanceStatus.PASSED
    assert report.level.value == "mock_verified"
