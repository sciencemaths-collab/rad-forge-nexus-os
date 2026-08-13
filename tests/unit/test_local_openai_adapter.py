import asyncio
from collections.abc import Coroutine, Mapping
from typing import Any

import pytest

from nexus_os.domain import RunId, TaskId, TaskStatus, TraceId
from nexus_os.local_openai_adapter import LocalOpenAIAdapter, LocalOpenAITransport
from nexus_os.providers import AdapterError, ConformanceLevel, ProviderEventKind, ProviderTask
from nexus_os.secrets import SecretResolver


def execute[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


def task(identifier: str = "local-task-1") -> ProviderTask:
    return ProviderTask(
        identifier,
        RunId.parse("00000000-0000-4000-8000-000000000001"),
        TaskId("draft_specification"),
        TraceId("1" * 32),
        "reason",
        {
            "system": "Return a candidate specification.",
            "prompt": "Draft the objective.",
            "api_token": "must-not-cross-boundary",
        },
        60,
    )


class FakeTransport(LocalOpenAITransport):
    def __init__(self, *, finish_reason: str = "stop") -> None:
        self.finish_reason = finish_reason
        self.health_calls: list[tuple[str, str | None]] = []
        self.requests: list[tuple[str, Mapping[str, object], str | None, int]] = []

    async def health(self, base_url: str, api_key: str | None, timeout_seconds: int) -> bool:
        self.health_calls.append((base_url, api_key))
        return True

    async def create_chat_completion(
        self,
        base_url: str,
        request: Mapping[str, object],
        api_key: str | None,
        timeout_seconds: int,
    ) -> Mapping[str, Any]:
        self.requests.append((base_url, request, api_key, timeout_seconds))
        return {
            "id": "chatcmpl-local-1",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": self.finish_reason,
                    "message": {"role": "assistant", "content": "candidate output"},
                }
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11},
        }


def adapter(
    transport: LocalOpenAITransport, *, credential: str | None = None
) -> LocalOpenAIAdapter:
    return LocalOpenAIAdapter(
        base_url="http://127.0.0.1:11434/v1",
        model="local-model:8b",
        credential=credential,
        resolver=SecretResolver(environment={"LOCAL_MODEL_KEY": "fixture-key"}),
        transport=transport,
    )


def test_success_maps_chat_completion_to_normalized_lifecycle_without_api_key() -> None:
    transport = FakeTransport()
    subject = adapter(transport)
    item = task()

    assert execute(subject.healthcheck()).value == "HEALTHY"
    assert execute(subject.run(item)) == item.provider_task_id
    events = execute(_collect(subject.stream_events(item.provider_task_id)))
    result = execute(subject.result(item.provider_task_id))

    assert [event.kind for event in events] == [
        ProviderEventKind.ACCEPTED,
        ProviderEventKind.STARTED,
        ProviderEventKind.COMPLETED,
    ]
    assert result.status is TaskStatus.SUCCEEDED
    assert result.usage.total_tokens == 11
    assert result.metadata["output_text"] == "candidate output"
    assert transport.health_calls == [("http://127.0.0.1:11434/v1", None)]
    request = transport.requests[0][1]
    assert request["model"] == "local-model:8b"
    assert request["messages"] == [
        {"role": "system", "content": "Return a candidate specification."},
        {"role": "user", "content": "Draft the objective."},
    ]
    assert "tools" not in request
    assert "api_token" not in str(request)
    assert subject.descriptor().credential is None
    assert subject.descriptor().conformance is ConformanceLevel.UNVERIFIED
    assert subject.descriptor().capabilities.supports_resume is False


def test_optional_opaque_credential_is_resolved_only_for_transport_calls() -> None:
    transport = FakeTransport()
    subject = adapter(transport, credential="env:LOCAL_MODEL_KEY")
    item = task("local-key-task")

    execute(subject.healthcheck())
    execute(subject.run(item))

    assert transport.health_calls[0][1] == "fixture-key"
    assert transport.requests[0][2] == "fixture-key"
    assert subject.descriptor().credential == "env:LOCAL_MODEL_KEY"


def test_truncation_duplicate_unknown_and_resume_fail_safely() -> None:
    subject = adapter(FakeTransport(finish_reason="length"))
    item = task()
    execute(subject.run(item))
    result = execute(subject.result(item.provider_task_id))
    assert result.status is TaskStatus.FAILED
    assert result.failure is not None
    with pytest.raises(AdapterError, match="already exists"):
        execute(subject.run(item))
    with pytest.raises(AdapterError, match="unknown"):
        execute(subject.result("missing"))
    with pytest.raises(AdapterError, match="not supported"):
        execute(subject.resume(item.provider_task_id))


def test_terminal_cancel_is_idempotent_and_malformed_output_is_rejected() -> None:
    subject = adapter(FakeTransport())
    item = task()
    execute(subject.run(item))
    execute(subject.cancel(item.provider_task_id))
    execute(subject.cancel(item.provider_task_id))

    class Malformed(FakeTransport):
        async def create_chat_completion(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return {"id": "bad", "choices": []}

    with pytest.raises(AdapterError, match="invalid local provider response"):
        execute(adapter(Malformed()).run(task("malformed-task")))


def test_messages_reject_tool_roles_extra_fields_and_oversized_content() -> None:
    subject = adapter(FakeTransport())
    for identifier, messages in (
        ("local-tool-role", [{"role": "tool", "content": "result"}]),
        ("local-extra-field", [{"role": "user", "content": "hello", "tool": "shell"}]),
        ("local-oversized", [{"role": "user", "content": "x" * 100_001}]),
    ):
        item = ProviderTask(
            identifier,
            RunId.parse("00000000-0000-4000-8000-000000000001"),
            TaskId("draft_specification"),
            TraceId("1" * 32),
            "reason",
            {"messages": messages},
            60,
        )
        with pytest.raises(AdapterError, match="message"):
            execute(subject.run(item))


async def _collect(events):  # type: ignore[no-untyped-def]
    return [event async for event in events]
