"""Provider-neutral, bounded, and redacted telemetry ports."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from nexus_os.secrets import redact

_NAME = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
_SENSITIVE_ATTRIBUTE = re.compile(
    r"(?:prompt|raw|payload|user_data|authorization|credential|password|private_key|secret|token)",
    re.IGNORECASE,
)
_MAX_ATTRIBUTES = 64
_MAX_KEY_LENGTH = 64
_MAX_STRING_LENGTH = 512

type AttributeValue = str | int | float | bool | None


class AttributeError(ValueError):
    """Safe telemetry validation failure."""


class EventKind(StrEnum):
    TRACE_START = "TRACE_START"
    TRACE_END = "TRACE_END"
    LOG = "LOG"
    METRIC = "METRIC"


@dataclass(frozen=True, slots=True)
class TraceContext:
    trace_id: str
    operation: str


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    kind: EventKind
    timestamp: datetime
    name: str
    trace_id: str | None
    attributes: Mapping[str, AttributeValue]

    def canonical(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "name": self.name,
            "trace_id": self.trace_id,
            "attributes": dict(sorted(self.attributes.items())),
        }


@dataclass(frozen=True, slots=True)
class TelemetryHealth:
    exported: int
    export_failures: int
    last_failure: str | None


class TelemetryExporter(Protocol):
    """Port implemented by OpenTelemetry or another deployment adapter."""

    def export(self, event: TelemetryEvent) -> None: ...


class InMemoryExporter:
    """Deterministic test exporter; not a production buffer."""

    def __init__(self, *, capacity: int = 10_000) -> None:
        if not isinstance(capacity, int) or not 1 <= capacity <= 100_000:
            raise AttributeError("exporter capacity is invalid")
        self._capacity = capacity
        self._events: list[TelemetryEvent] = []

    @property
    def events(self) -> tuple[TelemetryEvent, ...]:
        return tuple(self._events)

    def export(self, event: TelemetryEvent) -> None:
        if len(self._events) >= self._capacity:
            raise RuntimeError("telemetry exporter capacity reached")
        self._events.append(event)


class Telemetry:
    """Safe event factory and failure-isolating exporter boundary."""

    def __init__(
        self,
        exporter: TelemetryExporter,
        *,
        clock: Callable[[], datetime],
        trace_id_factory: Callable[[], str],
        exact_secrets: frozenset[str] = frozenset(),
    ) -> None:
        self._exporter = exporter
        self._clock = clock
        self._trace_id_factory = trace_id_factory
        self._exact_secrets = exact_secrets
        self._active: set[str] = set()
        self._ended: set[str] = set()
        self._exported = 0
        self._export_failures = 0
        self._last_failure: str | None = None

    def start_trace(
        self, operation: str, attributes: Mapping[str, object] | None = None
    ) -> TraceContext:
        _valid_name(operation, "operation")
        trace_id = self._trace_id_factory()
        if not isinstance(trace_id, str) or _TRACE_ID.fullmatch(trace_id) is None:
            raise AttributeError("trace_id factory returned an invalid identifier")
        if trace_id in self._active or trace_id in self._ended:
            raise AttributeError("trace_id factory returned a duplicate identifier")
        context = TraceContext(trace_id, operation)
        self._active.add(trace_id)
        self._emit(EventKind.TRACE_START, operation, trace_id, attributes)
        return context

    def end_trace(
        self,
        trace: TraceContext,
        *,
        outcome: str,
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        self._require_active(trace)
        merged = dict(attributes or {})
        merged["outcome"] = outcome
        self._emit(EventKind.TRACE_END, trace.operation, trace.trace_id, merged)
        self._active.remove(trace.trace_id)
        self._ended.add(trace.trace_id)

    def log(
        self,
        trace: TraceContext,
        name: str,
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        self._require_active(trace)
        self._emit(EventKind.LOG, name, trace.trace_id, attributes)

    def metric(
        self,
        name: str,
        value: int | float,
        attributes: Mapping[str, object] | None = None,
        *,
        trace: TraceContext | None = None,
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AttributeError("metric value must be numeric")
        if not math.isfinite(float(value)):
            raise AttributeError("metric value must be finite")
        if trace is not None:
            self._require_active(trace)
        merged = dict(attributes or {})
        merged["value"] = value
        self._emit(EventKind.METRIC, name, None if trace is None else trace.trace_id, merged)

    def health(self) -> TelemetryHealth:
        return TelemetryHealth(self._exported, self._export_failures, self._last_failure)

    def _require_active(self, trace: TraceContext) -> None:
        if not isinstance(trace, TraceContext):
            raise AttributeError("trace context is invalid")
        if trace.trace_id in self._ended:
            raise AttributeError("trace is already ended")
        if trace.trace_id not in self._active:
            raise AttributeError("trace is not active")

    def _emit(
        self,
        kind: EventKind,
        name: str,
        trace_id: str | None,
        attributes: Mapping[str, object] | None,
    ) -> None:
        _valid_name(name, "event name")
        timestamp = self._clock()
        if (
            not isinstance(timestamp, datetime)
            or timestamp.tzinfo is None
            or timestamp.utcoffset() != UTC.utcoffset(timestamp)
        ):
            raise AttributeError("telemetry clock must return timezone-aware UTC")
        event = TelemetryEvent(
            kind,
            timestamp,
            name,
            trace_id,
            MappingProxyType(_safe_attributes(attributes or {}, self._exact_secrets)),
        )
        try:
            self._exporter.export(event)
        except Exception:
            self._export_failures += 1
            self._last_failure = "telemetry export failed"
        else:
            self._exported += 1


def _valid_name(value: object, label: str) -> None:
    if not isinstance(value, str) or _NAME.fullmatch(value) is None:
        raise AttributeError(f"{label} is invalid")


def _safe_attributes(
    attributes: Mapping[str, object], exact_secrets: frozenset[str]
) -> dict[str, AttributeValue]:
    if not isinstance(attributes, Mapping) or len(attributes) > _MAX_ATTRIBUTES:
        raise AttributeError("telemetry attribute limit exceeded")
    result: dict[str, AttributeValue] = {}
    for key, value in attributes.items():
        if not isinstance(key, str) or not key or len(key) > _MAX_KEY_LENGTH:
            raise AttributeError("telemetry attribute key is invalid")
        if _SENSITIVE_ATTRIBUTE.search(key):
            result[key] = "<redacted>"
            continue
        safe = redact(value, exact_values=exact_secrets)
        if safe is not None and not isinstance(safe, (str, bool, int, float)):
            raise AttributeError("telemetry attributes must be bounded scalar values")
        if isinstance(safe, float) and not math.isfinite(safe):
            raise AttributeError("telemetry numeric attributes must be finite")
        if isinstance(safe, str) and len(safe) > _MAX_STRING_LENGTH:
            raise AttributeError("telemetry string attribute exceeds limit")
        result[key] = safe
    return result
