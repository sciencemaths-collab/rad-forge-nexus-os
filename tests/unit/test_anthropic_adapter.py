import asyncio
from collections.abc import Coroutine, Mapping
from typing import Any

import pytest

from nexus_os.anthropic_adapter import AnthropicAdapter, AnthropicTransport
from nexus_os.domain import RunId, TaskId, TaskStatus, TraceId
from nexus_os.providers import AdapterError, ConformanceLevel, ProviderEventKind, ProviderTask
from nexus_os.secrets import SecretResolver


def execute[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


def task(identifier: str = "anthropic-task-1") -> ProviderTask:
    return ProviderTask(
        identifier,
        RunId.parse("00000000-0000-4000-8000-000000000001"),
        TaskId("implement_code"),
        TraceId("1" * 32),
        "implement",
        {"instructions": "implement the validated task"},
        60,
    )


class FakeTransport(AnthropicTransport):
    def __init__(self, *, stop_reason: str = "end_turn") -> None:
        self.stop_reason = stop_reason
        self.requests: list[Mapping[str, object]] = []
        self.keys: list[str] = []

    async def health(self, api_key: str) -> bool:
        self.keys.append(api_key)
        return True

    async def create(self, request: Mapping[str, object], api_key: str) -> Mapping[str, Any]:
        self.requests.append(request)
        self.keys.append(api_key)
        return {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "stop_reason": self.stop_reason,
            "content": [{"type": "text", "text": "done"}],
            "usage": {"input_tokens": 10, "output_tokens": 4},
        }


def adapter(transport: AnthropicTransport) -> AnthropicAdapter:
    return AnthropicAdapter(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        credential="env:ANTHROPIC_API_KEY",
        resolver=SecretResolver(environment={"ANTHROPIC_API_KEY": "fixture-key"}),
        transport=transport,
    )


def test_success_maps_message_to_normalized_lifecycle() -> None:
    transport = FakeTransport()
    subject = adapter(transport)
    item = task()

    assert execute(subject.run(item)) == item.provider_task_id
    events = execute(_collect(subject.stream_events(item.provider_task_id)))
    result = execute(subject.result(item.provider_task_id))

    assert [event.kind for event in events] == [
        ProviderEventKind.ACCEPTED,
        ProviderEventKind.STARTED,
        ProviderEventKind.COMPLETED,
    ]
    assert result.status is TaskStatus.SUCCEEDED
    assert result.usage.total_tokens == 14
    assert transport.requests[0]["model"] == "claude-sonnet-4-20250514"
    assert transport.requests[0]["max_tokens"] == 4096
    assert subject.descriptor().conformance is ConformanceLevel.UNVERIFIED
    assert subject.descriptor().capabilities.supports_resume is False


def test_truncation_and_refusal_are_normalized_failures() -> None:
    for reason in ("max_tokens", "refusal"):
        subject = adapter(FakeTransport(stop_reason=reason))
        execute(subject.run(task(f"anthropic-{reason.replace('_', '-')}")))
        result = execute(subject.result(f"anthropic-{reason.replace('_', '-')}"))
        assert result.status is TaskStatus.FAILED
        assert result.failure is not None


def test_resume_is_explicitly_unsupported_and_cancel_terminal_is_idempotent() -> None:
    subject = adapter(FakeTransport())
    item = task()
    execute(subject.run(item))
    execute(subject.cancel(item.provider_task_id))
    execute(subject.cancel(item.provider_task_id))
    with pytest.raises(AdapterError, match="not supported"):
        execute(subject.resume(item.provider_task_id))


def test_malformed_duplicate_and_unknown_operations_fail_safely() -> None:
    class Malformed(FakeTransport):
        async def create(self, request, api_key):  # type: ignore[no-untyped-def]
            return {"id": "bad", "type": "unexpected", "stop_reason": "end_turn"}

    with pytest.raises(AdapterError, match="invalid provider message"):
        execute(adapter(Malformed()).run(task()))

    subject = adapter(FakeTransport())
    item = task()
    execute(subject.run(item))
    with pytest.raises(AdapterError, match="already exists"):
        execute(subject.run(item))
    with pytest.raises(AdapterError, match="unknown"):
        execute(subject.result("missing"))


async def _collect(events):  # type: ignore[no-untyped-def]
    return [event async for event in events]
