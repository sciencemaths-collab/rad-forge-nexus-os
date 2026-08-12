"""Deterministic in-process AgentAdapter used for conformance and failure tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any

from nexus_os.domain import Failure, FailureClass, TaskStatus
from nexus_os.providers import (
    AdapterError,
    HealthState,
    ProviderCapabilities,
    ProviderEvent,
    ProviderEventKind,
    ProviderResult,
    ProviderTask,
    Usage,
)
from nexus_os.secrets import redact

_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class MockScenario:
    """Bounded script selected by normalized provider operation."""

    status: TaskStatus | None = TaskStatus.SUCCEEDED
    progress: tuple[Mapping[str, Any], ...] = ({"message": "scripted progress"},)
    usage: Usage = field(default_factory=lambda: Usage(8, 5, 0.0))
    metadata: Mapping[str, Any] = field(default_factory=lambda: {"scenario": "success"})
    failure_value: Failure | None = None

    def __post_init__(self) -> None:
        if self.status is not None and not self.status.is_terminal:
            raise AdapterError("mock scenario status must be terminal or pending")
        if self.status is TaskStatus.FAILED and self.failure_value is None:
            raise AdapterError("failed mock scenario requires a failure")
        if self.status is not TaskStatus.FAILED and self.failure_value is not None:
            raise AdapterError("failure is valid only for a failed mock scenario")
        if len(self.progress) > 100:
            raise AdapterError("mock scenario has too many progress events")
        safe_progress: list[Mapping[str, Any]] = []
        for payload in self.progress:
            safe = redact(payload)
            if not isinstance(safe, dict):
                raise AdapterError("mock progress payload must be an object")
            safe_progress.append(MappingProxyType(safe))
        safe_metadata = redact(self.metadata)
        if not isinstance(safe_metadata, dict):
            raise AdapterError("mock metadata must be an object")
        object.__setattr__(self, "progress", tuple(safe_progress))
        object.__setattr__(self, "metadata", MappingProxyType(safe_metadata))

    @classmethod
    def pending(cls) -> MockScenario:
        return cls(status=None, progress=(), metadata={"scenario": "pending"})

    @classmethod
    def failure(
        cls,
        classification: FailureClass,
        code: str,
        message: str,
        *,
        retryable: bool,
        metadata: Mapping[str, Any] | None = None,
    ) -> MockScenario:
        return cls(
            status=TaskStatus.FAILED,
            metadata=metadata or {"scenario": "failure"},
            failure_value=Failure(classification, code, message, retryable),
        )


@dataclass(slots=True)
class _Execution:
    task: ProviderTask
    scenario: MockScenario
    events: list[ProviderEvent]
    result: ProviderResult | None = None


class DeterministicMockAdapter:
    """Protocol-faithful mock with no clocks, randomness, I/O, or credentials."""

    def __init__(
        self,
        *,
        scenarios: Mapping[str, MockScenario] | None = None,
        supports_resume: bool = False,
        health: HealthState = HealthState.HEALTHY,
        strict_operations: bool = False,
    ) -> None:
        if len(scenarios or {}) > 128:
            raise AdapterError("too many mock scenarios")
        self._scenarios = dict(scenarios or {})
        self._supports_resume = supports_resume
        self._health = health
        self._strict_operations = strict_operations
        self._executions: dict[str, _Execution] = {}

    async def healthcheck(self) -> HealthState:
        return self._health

    async def capabilities(self) -> ProviderCapabilities:
        names = {"stream", "cancel", "deterministic"}
        if self._supports_resume:
            names.add("resume")
        return ProviderCapabilities(frozenset(names), self._supports_resume)

    async def run(self, task: ProviderTask) -> str:
        if task.provider_task_id in self._executions:
            raise AdapterError("provider task already exists")
        if self._strict_operations and task.operation not in self._scenarios:
            raise AdapterError("operation has no configured mock scenario")
        scenario = self._scenarios.get(task.operation, MockScenario())
        execution = _Execution(task, scenario, [])
        self._executions[task.provider_task_id] = execution
        self._append(execution, ProviderEventKind.ACCEPTED, {"operation": task.operation})
        self._append(execution, ProviderEventKind.STARTED, {})
        for payload in scenario.progress:
            self._append(execution, ProviderEventKind.PROGRESS, payload)
        if scenario.status is not None:
            self._finish(execution, scenario.status)
        return task.provider_task_id

    async def stream_events(self, provider_task_id: str) -> AsyncIterator[ProviderEvent]:
        execution = self._get(provider_task_id)
        for event in tuple(execution.events):
            yield event

    async def result(self, provider_task_id: str) -> ProviderResult:
        execution = self._get(provider_task_id)
        if execution.result is None:
            raise AdapterError("provider task is not terminal")
        return execution.result

    async def cancel(self, provider_task_id: str) -> None:
        execution = self._get(provider_task_id)
        if execution.result is None:
            self._finish(execution, TaskStatus.CANCELLED)

    async def resume(self, provider_task_id: str) -> str:
        if not self._supports_resume:
            raise AdapterError("resume is not supported")
        self._get(provider_task_id)
        return provider_task_id

    def _get(self, provider_task_id: str) -> _Execution:
        try:
            return self._executions[provider_task_id]
        except KeyError as exc:
            raise AdapterError("unknown provider task") from exc

    @staticmethod
    def _append(execution: _Execution, kind: ProviderEventKind, payload: Mapping[str, Any]) -> None:
        sequence = len(execution.events) + 1
        execution.events.append(
            ProviderEvent.create(
                execution.task.provider_task_id,
                sequence,
                _EPOCH + timedelta(microseconds=sequence),
                kind,
                payload,
                execution.task.trace_id,
            )
        )

    def _finish(self, execution: _Execution, status: TaskStatus) -> None:
        kinds = {
            TaskStatus.SUCCEEDED: ProviderEventKind.COMPLETED,
            TaskStatus.FAILED: ProviderEventKind.FAILED,
            TaskStatus.CANCELLED: ProviderEventKind.CANCELLED,
            TaskStatus.SKIPPED: ProviderEventKind.CANCELLED,
        }
        try:
            event_kind = kinds[status]
        except KeyError as exc:
            raise AdapterError("unsupported mock terminal status") from exc
        self._append(execution, event_kind, {"status": status.value})
        failure = execution.scenario.failure_value if status is TaskStatus.FAILED else None
        execution.result = ProviderResult(
            execution.task.provider_task_id,
            status,
            usage=execution.scenario.usage,
            metadata=execution.scenario.metadata,
            failure=failure,
        )
