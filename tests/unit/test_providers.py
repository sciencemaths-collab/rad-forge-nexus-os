from datetime import UTC, datetime

import pytest

from nexus_os.domain import RunId, TaskId, TraceId
from nexus_os.providers import (
    AdapterError,
    ConformanceLevel,
    HealthState,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderEvent,
    ProviderEventKind,
    ProviderRegistry,
    ProviderTask,
    Usage,
)


def descriptor(provider_id: str = "mock") -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id,
        "nexus.mock",
        "1.0",
        ProviderCapabilities(frozenset({"stream", "cancel"}), supports_resume=False),
        ConformanceLevel.UNVERIFIED,
        HealthState.HEALTHY,
    )


def test_descriptor_is_schema_aligned_and_secret_reference_only() -> None:
    item = descriptor()
    assert item.canonical()["capabilities"] == ["cancel", "stream"]
    assert item.canonical()["supports_resume"] is False
    with pytest.raises(AdapterError, match="credential"):
        ProviderDescriptor(
            "mock", "nexus.mock", "1.0", item.capabilities, credential="literal-secret"
        )


def test_task_and_event_are_bounded_immutable_and_redacted() -> None:
    task = ProviderTask(
        "provider-task-1",
        RunId.parse("00000000-0000-4000-8000-000000000001"),
        TaskId("build_task"),
        TraceId("1" * 32),
        "implement",
        {"spec_digest": "sha256:" + "2" * 64},
        60,
    )
    event = ProviderEvent.create(
        task.provider_task_id,
        1,
        datetime(2026, 8, 12, tzinfo=UTC),
        ProviderEventKind.PROGRESS,
        {"message": "working", "api_token": "canary"},
        task.trace_id,
    )
    assert event.payload["api_token"] == "<redacted>"  # noqa: S105
    with pytest.raises(TypeError):
        event.payload["message"] = "changed"  # type: ignore[index]


def test_usage_rejects_hostile_numbers() -> None:
    assert Usage(1, 2, 0.25).total_tokens == 3
    with pytest.raises(AdapterError, match="finite"):
        Usage(1, 2, float("nan"))


def test_registry_rejects_duplicates_and_unknown_provider() -> None:
    registry = ProviderRegistry()
    adapter = object()
    registry.register(descriptor(), adapter)
    assert registry.get("mock") is adapter
    assert registry.descriptors() == (descriptor(),)
    with pytest.raises(AdapterError, match="already registered"):
        registry.register(descriptor(), object())
    with pytest.raises(AdapterError, match="not registered"):
        registry.get("missing")
