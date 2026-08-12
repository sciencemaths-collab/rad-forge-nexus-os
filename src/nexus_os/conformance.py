"""Deterministic, provider-neutral AgentAdapter conformance harness."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from nexus_os.domain import RunId, TaskId, TaskStatus, TraceId
from nexus_os.providers import (
    AdapterError,
    AgentAdapter,
    ConformanceLevel,
    HealthState,
    ProviderCapabilities,
    ProviderEvent,
    ProviderEventKind,
    ProviderResult,
    ProviderTask,
)

_T = TypeVar("_T")
_RUN_ID = RunId.parse("00000000-0000-4000-8000-000000000001")
_TRACE_ID = TraceId("1" * 32)


class ConformanceStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ConformanceCase:
    name: str
    status: ConformanceStatus
    details: tuple[str, ...] = ()

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status.value,
            "details": list(self.details),
        }


@dataclass(frozen=True, slots=True)
class ConformanceReport:
    status: ConformanceStatus
    level: ConformanceLevel
    cases: tuple[ConformanceCase, ...]
    report_digest: str

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(case.status is ConformanceStatus.PASSED for case in self.cases)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    def canonical(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "status": self.status.value,
            "level": self.level.value,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "cases": [case.canonical() for case in self.cases],
            "report_digest": self.report_digest,
        }


class _CaseFailure(Exception):
    pass


class ConformanceHarness:
    """Exercise an adapter factory against the normalized protocol contract."""

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 300
        ):
            raise ValueError("timeout_seconds must be finite and from 0 to 300")
        self._timeout = float(timeout_seconds)

    async def run(self, factory: Callable[[], AgentAdapter]) -> ConformanceReport:
        checks: tuple[tuple[str, Callable[[AgentAdapter], Awaitable[tuple[str, ...]]]], ...] = (
            ("health_and_capabilities", self._health_and_capabilities),
            ("successful_lifecycle", self._successful_lifecycle),
            ("cancellation", self._cancellation),
            ("resume_contract", self._resume_contract),
            ("unknown_task_safety", self._unknown_task_safety),
        )
        cases: list[ConformanceCase] = []
        for name, check in checks:
            try:
                adapter = factory()
                details = await check(adapter)
            except TimeoutError:
                cases.append(
                    ConformanceCase(name, ConformanceStatus.FAILED, ("operation timed out",))
                )
            except _CaseFailure as exc:
                cases.append(ConformanceCase(name, ConformanceStatus.FAILED, (str(exc),)))
            except Exception:
                cases.append(
                    ConformanceCase(name, ConformanceStatus.FAILED, ("adapter contract error",))
                )
            else:
                cases.append(ConformanceCase(name, ConformanceStatus.PASSED, details))

        frozen = tuple(cases)
        status = (
            ConformanceStatus.PASSED
            if all(case.status is ConformanceStatus.PASSED for case in frozen)
            else ConformanceStatus.FAILED
        )
        level = (
            ConformanceLevel.MOCK_VERIFIED
            if status is ConformanceStatus.PASSED
            else ConformanceLevel.UNVERIFIED
        )
        payload = {
            "schema_version": "1.0",
            "status": status.value,
            "level": level.value,
            "cases": [case.canonical() for case in frozen],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
        return ConformanceReport(status, level, frozen, digest)

    async def _wait(self, operation: Awaitable[_T]) -> _T:
        return await asyncio.wait_for(operation, timeout=self._timeout)

    async def _collect(self, events: AsyncIterator[ProviderEvent]) -> tuple[ProviderEvent, ...]:
        async def consume() -> tuple[ProviderEvent, ...]:
            return tuple([event async for event in events])

        return await self._wait(consume())

    @staticmethod
    def _task(suffix: str) -> ProviderTask:
        return ProviderTask(
            f"conformance-{suffix}",
            _RUN_ID,
            TaskId(f"conformance_{suffix}"),
            _TRACE_ID,
            "conformance",
            {"prompt": "CONFORMANCE_SECRET_CANARY", "api_token": "fixture"},
            30,
        )

    async def _health_and_capabilities(self, adapter: AgentAdapter) -> tuple[str, ...]:
        health = await self._wait(adapter.healthcheck())
        capabilities = await self._wait(adapter.capabilities())
        if not isinstance(health, HealthState) or not isinstance(
            capabilities, ProviderCapabilities
        ):
            raise _CaseFailure("health or capabilities type is invalid")
        return ("discovery_verified",)

    async def _successful_lifecycle(self, adapter: AgentAdapter) -> tuple[str, ...]:
        task = self._task("success")
        identity = await self._wait(adapter.run(task))
        if identity != task.provider_task_id:
            raise _CaseFailure("provider task identity mismatch")
        events = await self._collect(adapter.stream_events(identity))
        result = await self._wait(adapter.result(identity))
        self._validate_lifecycle(task, events, result)
        return ("normalized_lifecycle_verified",)

    @staticmethod
    def _validate_lifecycle(
        task: ProviderTask, events: tuple[ProviderEvent, ...], result: ProviderResult
    ) -> None:
        if not events or [event.sequence for event in events] != list(range(1, len(events) + 1)):
            raise _CaseFailure("event sequence is not contiguous")
        if events[0].kind is not ProviderEventKind.ACCEPTED:
            raise _CaseFailure("event sequence does not begin with acceptance")
        if any(
            event.provider_task_id != task.provider_task_id or event.trace_id != task.trace_id
            for event in events
        ):
            raise _CaseFailure("event identity or trace mismatch")
        terminal = {
            TaskStatus.SUCCEEDED: ProviderEventKind.COMPLETED,
            TaskStatus.FAILED: ProviderEventKind.FAILED,
            TaskStatus.CANCELLED: ProviderEventKind.CANCELLED,
            TaskStatus.SKIPPED: ProviderEventKind.CANCELLED,
        }
        if result.provider_task_id != task.provider_task_id:
            raise _CaseFailure("result identity mismatch")
        if events[-1].kind is not terminal[result.status]:
            raise _CaseFailure("terminal event and result disagree")

    async def _cancellation(self, adapter: AgentAdapter) -> tuple[str, ...]:
        task = self._task("cancel")
        identity = await self._wait(adapter.run(task))
        await self._wait(adapter.cancel(identity))
        await self._wait(adapter.cancel(identity))
        result = await self._wait(adapter.result(identity))
        if not result.status.is_terminal:
            raise _CaseFailure("cancellation did not preserve a terminal result")
        return ("idempotent_cancel_verified",)

    async def _resume_contract(self, adapter: AgentAdapter) -> tuple[str, ...]:
        task = self._task("resume")
        identity = await self._wait(adapter.run(task))
        capabilities = await self._wait(adapter.capabilities())
        if capabilities.supports_resume:
            resumed = await self._wait(adapter.resume(identity))
            if resumed != identity:
                raise _CaseFailure("resume identity mismatch")
            return ("advertised_and_verified",)
        try:
            await self._wait(adapter.resume(identity))
        except AdapterError:
            return ("unsupported_and_rejected",)
        raise _CaseFailure("unsupported resume was accepted")

    async def _unknown_task_safety(self, adapter: AgentAdapter) -> tuple[str, ...]:
        rejected = 0
        try:
            await self._wait(adapter.result("conformance-unknown"))
        except AdapterError:
            rejected += 1
        try:
            await self._wait(adapter.cancel("conformance-unknown"))
        except AdapterError:
            rejected += 1
        if rejected != 2:
            raise _CaseFailure("unknown provider task was not rejected")
        return ("unknown_task_rejected",)
