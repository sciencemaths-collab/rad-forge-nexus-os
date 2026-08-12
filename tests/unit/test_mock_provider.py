import asyncio
from collections.abc import AsyncIterator, Coroutine
from typing import Any

import pytest

from nexus_os.domain import FailureClass, RunId, TaskId, TaskStatus, TraceId
from nexus_os.mock_provider import DeterministicMockAdapter, MockScenario
from nexus_os.providers import AdapterError, HealthState, ProviderEventKind, ProviderTask


def task(provider_task_id: str = "provider-task-1", operation: str = "implement") -> ProviderTask:
    return ProviderTask(
        provider_task_id,
        RunId.parse("00000000-0000-4000-8000-000000000001"),
        TaskId("build_task"),
        TraceId("1" * 32),
        operation,
        {"spec_digest": "sha256:" + "2" * 64},
        60,
    )


def execute[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


async def collect[T](events: AsyncIterator[T]) -> list[T]:
    return [event async for event in events]


def test_success_is_deterministic_and_protocol_faithful() -> None:
    adapter = DeterministicMockAdapter()
    item = task()

    assert execute(adapter.healthcheck()) is HealthState.HEALTHY
    assert execute(adapter.run(item)) == item.provider_task_id
    events = execute(collect(adapter.stream_events(item.provider_task_id)))
    result = execute(adapter.result(item.provider_task_id))

    assert [event.kind for event in events] == [
        ProviderEventKind.ACCEPTED,
        ProviderEventKind.STARTED,
        ProviderEventKind.PROGRESS,
        ProviderEventKind.COMPLETED,
    ]
    assert [event.sequence for event in events] == [1, 2, 3, 4]
    assert all(event.trace_id == item.trace_id for event in events)
    assert result.status is TaskStatus.SUCCEEDED
    assert result.metadata["scenario"] == "success"


def test_failure_injection_is_normalized_and_redacted() -> None:
    adapter = DeterministicMockAdapter(
        scenarios={
            "implement": MockScenario.failure(
                FailureClass.PROVIDER,
                "provider_unavailable",
                "scripted provider failure",
                retryable=True,
                metadata={"api_token": "canary", "reason": "fixture"},
            )
        }
    )
    item = task()

    execute(adapter.run(item))
    events = execute(collect(adapter.stream_events(item.provider_task_id)))
    result = execute(adapter.result(item.provider_task_id))

    assert events[-1].kind is ProviderEventKind.FAILED
    assert result.status is TaskStatus.FAILED
    assert result.failure is not None
    assert result.failure.code == "provider_unavailable"
    assert result.metadata["api_token"] == "<redacted>"  # noqa: S105


def test_pending_scenario_can_be_cancelled_idempotently() -> None:
    adapter = DeterministicMockAdapter(
        scenarios={"implement": MockScenario.pending()}, supports_resume=True
    )
    item = task()
    execute(adapter.run(item))

    with pytest.raises(AdapterError, match="not terminal"):
        execute(adapter.result(item.provider_task_id))
    execute(adapter.cancel(item.provider_task_id))
    execute(adapter.cancel(item.provider_task_id))

    result = execute(adapter.result(item.provider_task_id))
    events = execute(collect(adapter.stream_events(item.provider_task_id)))
    assert result.status is TaskStatus.CANCELLED
    assert events[-1].kind is ProviderEventKind.CANCELLED


def test_resume_is_capability_gated_and_deterministic() -> None:
    item = task()
    unsupported = DeterministicMockAdapter(
        scenarios={"implement": MockScenario.pending()}, supports_resume=False
    )
    execute(unsupported.run(item))
    with pytest.raises(AdapterError, match="not supported"):
        execute(unsupported.resume(item.provider_task_id))

    supported = DeterministicMockAdapter(
        scenarios={"implement": MockScenario.pending()}, supports_resume=True
    )
    execute(supported.run(item))
    assert execute(supported.resume(item.provider_task_id)) == item.provider_task_id
    assert execute(supported.resume(item.provider_task_id)) == item.provider_task_id


def test_duplicate_and_unknown_task_operations_fail_safely() -> None:
    adapter = DeterministicMockAdapter()
    item = task()
    execute(adapter.run(item))
    with pytest.raises(AdapterError, match="already exists"):
        execute(adapter.run(item))
    with pytest.raises(AdapterError, match="unknown"):
        execute(collect(adapter.stream_events("missing")))
    with pytest.raises(AdapterError, match="unknown"):
        execute(adapter.result("missing"))
    with pytest.raises(AdapterError, match="unknown"):
        execute(adapter.cancel("missing"))
