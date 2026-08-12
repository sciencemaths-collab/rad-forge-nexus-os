"""Provider-neutral AgentAdapter SDK and normalized boundary models."""

from __future__ import annotations

import math
import re
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

from nexus_os.domain import ArtifactRef, Failure, RunId, TaskId, TaskStatus, TraceId
from nexus_os.secrets import SecretReference, redact

_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_TOKEN = re.compile(r"^[a-z][a-z0-9_.-]{1,127}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_PROVIDER_TASK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class AdapterError(ValueError):
    """Safe normalized provider-boundary failure."""


class HealthState(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class ConformanceLevel(StrEnum):
    UNVERIFIED = "unverified"
    MOCK_VERIFIED = "mock_verified"
    LIVE_VERIFIED = "live_verified"
    PRODUCTION_QUALIFIED = "production_qualified"


class ProviderEventKind(StrEnum):
    ACCEPTED = "ACCEPTED"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    ARTIFACT = "ARTIFACT"
    LOG = "LOG"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    names: frozenset[str]
    supports_resume: bool = False

    def __post_init__(self) -> None:
        if len(self.names) > 128 or any(not _TOKEN.fullmatch(item) for item in self.names):
            raise AdapterError("provider capabilities are invalid")
        if not isinstance(self.supports_resume, bool):
            raise AdapterError("supports_resume must be boolean")


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    provider_id: str
    adapter: str
    adapter_version: str
    capabilities: ProviderCapabilities
    conformance: ConformanceLevel = ConformanceLevel.UNVERIFIED
    health: HealthState = HealthState.UNKNOWN
    credential: str | None = None

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.provider_id):
            raise AdapterError("provider_id is invalid")
        if not _TOKEN.fullmatch(self.adapter):
            raise AdapterError("adapter is invalid")
        if not _VERSION.fullmatch(self.adapter_version):
            raise AdapterError("adapter_version is invalid")
        if self.credential is not None:
            try:
                SecretReference.parse(self.credential)
            except ValueError as exc:
                raise AdapterError("credential must be an opaque secret reference") from exc

    def canonical(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "provider_id": self.provider_id,
            "adapter": self.adapter,
            "adapter_version": self.adapter_version,
            "capabilities": sorted(self.capabilities.names),
            "conformance": self.conformance.value,
            "health": self.health.value,
            "supports_resume": self.capabilities.supports_resume,
            "credential": self.credential,
        }


@dataclass(frozen=True, slots=True)
class ProviderTask:
    provider_task_id: str
    run_id: RunId
    task_id: TaskId
    trace_id: TraceId
    operation: str
    input: Mapping[str, Any]
    timeout_seconds: int

    def __post_init__(self) -> None:
        if not _PROVIDER_TASK.fullmatch(self.provider_task_id):
            raise AdapterError("provider_task_id is invalid")
        if not _TOKEN.fullmatch(self.operation):
            raise AdapterError("operation is invalid")
        if not isinstance(self.timeout_seconds, int) or not 1 <= self.timeout_seconds <= 86_400:
            raise AdapterError("timeout_seconds must be from 1 to 86400")
        safe = redact(self.input)
        if not isinstance(safe, dict):
            raise AdapterError("provider task input must be an object")
        object.__setattr__(self, "input", MappingProxyType(safe))


@dataclass(frozen=True, slots=True)
class ProviderEvent:
    provider_task_id: str
    sequence: int
    timestamp: datetime
    kind: ProviderEventKind
    payload: Mapping[str, Any]
    trace_id: TraceId | None = None

    @classmethod
    def create(
        cls,
        provider_task_id: str,
        sequence: int,
        timestamp: datetime,
        kind: ProviderEventKind,
        payload: Mapping[str, Any],
        trace_id: TraceId | None = None,
    ) -> ProviderEvent:
        safe = redact(payload)
        if not isinstance(safe, dict):
            raise AdapterError("provider event payload must be an object")
        return cls(provider_task_id, sequence, timestamp, kind, MappingProxyType(safe), trace_id)

    def __post_init__(self) -> None:
        if not _PROVIDER_TASK.fullmatch(self.provider_task_id):
            raise AdapterError("provider_task_id is invalid")
        if not isinstance(self.sequence, int) or not 1 <= self.sequence <= 1_000_000:
            raise AdapterError("provider event sequence is invalid")
        if (
            not isinstance(self.timestamp, datetime)
            or self.timestamp.tzinfo is None
            or self.timestamp.utcoffset() != UTC.utcoffset(self.timestamp)
        ):
            raise AdapterError("provider event timestamp must be UTC")


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float

    def __post_init__(self) -> None:
        tokens = (self.input_tokens, self.output_tokens)
        if any(not isinstance(item, int) or item < 0 for item in tokens):
            raise AdapterError("token usage must be non-negative integers")
        if not math.isfinite(self.estimated_cost_usd) or self.estimated_cost_usd < 0:
            raise AdapterError("estimated cost must be finite and non-negative")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider_task_id: str
    status: TaskStatus
    artifacts: tuple[ArtifactRef, ...] = ()
    usage: Usage = field(default_factory=lambda: Usage(0, 0, 0.0))
    metadata: Mapping[str, Any] = field(default_factory=dict)
    failure: Failure | None = None

    def __post_init__(self) -> None:
        if not _PROVIDER_TASK.fullmatch(self.provider_task_id) or not self.status.is_terminal:
            raise AdapterError("provider result identity or status is invalid")
        if (self.status is TaskStatus.FAILED) != (self.failure is not None):
            raise AdapterError("failure is required only for failed provider results")
        safe = redact(self.metadata)
        if not isinstance(safe, dict):
            raise AdapterError("provider metadata must be an object")
        object.__setattr__(self, "metadata", MappingProxyType(safe))


class AgentAdapter(Protocol):
    async def healthcheck(self) -> HealthState: ...
    async def capabilities(self) -> ProviderCapabilities: ...
    async def run(self, task: ProviderTask) -> str: ...
    def stream_events(self, provider_task_id: str) -> AsyncIterator[ProviderEvent]: ...
    async def result(self, provider_task_id: str) -> ProviderResult: ...
    async def cancel(self, provider_task_id: str) -> None: ...
    async def resume(self, provider_task_id: str) -> str: ...


class ProviderRegistry:
    def __init__(self) -> None:
        self._items: dict[str, tuple[ProviderDescriptor, object]] = {}

    def register(self, descriptor: ProviderDescriptor, adapter: object) -> None:
        if descriptor.provider_id in self._items:
            raise AdapterError("provider is already registered")
        self._items[descriptor.provider_id] = (descriptor, adapter)

    def get(self, provider_id: str) -> object:
        try:
            return self._items[provider_id][1]
        except KeyError as exc:
            raise AdapterError("provider is not registered") from exc

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(self._items[key][0] for key in sorted(self._items))
