import asyncio
from collections.abc import Coroutine, Mapping
from typing import Any

import pytest

from nexus_os.domain import RunId, TaskId, TaskStatus, TraceId
from nexus_os.openai_adapter import OpenAIAdapter, OpenAITransport
from nexus_os.providers import AdapterError, ConformanceLevel, ProviderEventKind, ProviderTask
from nexus_os.secrets import SecretResolver


def execute[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


def task(identifier: str = "openai-task-1") -> ProviderTask:
    return ProviderTask(
        identifier,
        RunId.parse("00000000-0000-4000-8000-000000000001"),
        TaskId("implement_code"),
        TraceId("1" * 32),
        "implement",
        {"instructions": "implement the validated task", "spec_digest": "sha256:" + "2" * 64},
        60,
    )


class FakeTransport(OpenAITransport):
    def __init__(self, *, status: str = "completed") -> None:
        self.status = status
        self.requests: list[Mapping[str, object]] = []
        self.keys: list[str] = []

    async def health(self, api_key: str) -> bool:
        self.keys.append(api_key)
        return True

    async def create(self, request: Mapping[str, object], api_key: str) -> Mapping[str, Any]:
        self.requests.append(request)
        self.keys.append(api_key)
        return {
            "id": "resp_123",
            "status": self.status,
            "output_text": "done",
            "usage": {"input_tokens": 12, "output_tokens": 7},
        }

    async def retrieve(self, response_id: str, api_key: str) -> Mapping[str, Any]:
        return {"id": response_id, "status": self.status, "usage": {}}

    async def cancel_response(self, response_id: str, api_key: str) -> Mapping[str, Any]:
        self.status = "cancelled"
        return {"id": response_id, "status": "cancelled", "usage": {}}


def adapter(transport: OpenAITransport) -> OpenAIAdapter:
    return OpenAIAdapter(
        model="gpt-5.6",
        credential="env:OPENAI_API_KEY",
        resolver=SecretResolver(environment={"OPENAI_API_KEY": "test-key-material"}),
        transport=transport,
    )


def test_success_maps_responses_api_to_normalized_lifecycle() -> None:
    transport = FakeTransport()
    item = task()
    subject = adapter(transport)

    assert execute(subject.run(item)) == item.provider_task_id
    events = execute(_collect(subject.stream_events(item.provider_task_id)))
    result = execute(subject.result(item.provider_task_id))

    assert [event.kind for event in events] == [
        ProviderEventKind.ACCEPTED,
        ProviderEventKind.STARTED,
        ProviderEventKind.COMPLETED,
    ]
    assert result.status is TaskStatus.SUCCEEDED
    assert result.usage.total_tokens == 19
    assert transport.requests[0]["store"] is False
    assert transport.requests[0]["background"] is False
    assert result.metadata["output_text"] == "done"
    assert transport.requests[0]["model"] == "gpt-5.6"
    assert subject.descriptor().conformance is ConformanceLevel.UNVERIFIED


def test_pending_response_cancel_is_idempotent_and_resume_retrieves() -> None:
    transport = FakeTransport(status="in_progress")
    subject = adapter(transport)
    item = task()
    execute(subject.run(item))

    assert execute(subject.resume(item.provider_task_id)) == item.provider_task_id
    execute(subject.cancel(item.provider_task_id))
    execute(subject.cancel(item.provider_task_id))
    assert execute(subject.result(item.provider_task_id)).status is TaskStatus.CANCELLED


def test_duplicate_unknown_and_malformed_transport_outputs_fail_safely() -> None:
    subject = adapter(FakeTransport())
    item = task()
    execute(subject.run(item))
    with pytest.raises(AdapterError, match="already exists"):
        execute(subject.run(item))
    with pytest.raises(AdapterError, match="unknown"):
        execute(subject.result("missing"))

    class Malformed(FakeTransport):
        async def create(self, request, api_key):  # type: ignore[no-untyped-def]
            return {"id": "bad", "status": "surprise"}

    with pytest.raises(AdapterError, match="invalid provider response"):
        execute(adapter(Malformed()).run(task("openai-task-2")))


async def _collect(events):  # type: ignore[no-untyped-def]
    return [event async for event in events]
