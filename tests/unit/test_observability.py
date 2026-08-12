from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nexus_os.observability import (
    AttributeError,
    EventKind,
    InMemoryExporter,
    Telemetry,
    TelemetryEvent,
)


def clock() -> datetime:
    return datetime(2026, 8, 12, 15, tzinfo=UTC)


def test_correlated_trace_log_and_metric_are_exported() -> None:
    exporter = InMemoryExporter()
    telemetry = Telemetry(exporter, clock=clock, trace_id_factory=lambda: "1" * 32)
    trace = telemetry.start_trace("runtime.run", {"project_id": "demo", "run_id": "run-1"})
    telemetry.log(trace, "runtime.ready", {"state": "READY"})
    telemetry.metric("runtime.retry.count", 2, {"failure_class": "TRANSIENT"}, trace=trace)
    telemetry.end_trace(trace, outcome="PASS", attributes={"duration_ms": 12})

    assert [event.kind for event in exporter.events] == [
        EventKind.TRACE_START,
        EventKind.LOG,
        EventKind.METRIC,
        EventKind.TRACE_END,
    ]
    assert {event.trace_id for event in exporter.events} == {"1" * 32}
    assert exporter.events[-1].attributes["outcome"] == "PASS"


def test_sensitive_and_unbounded_attributes_are_rejected_or_redacted() -> None:
    exporter = InMemoryExporter()
    telemetry = Telemetry(exporter, clock=clock, trace_id_factory=lambda: "2" * 32)
    trace = telemetry.start_trace(
        "provider.call",
        {"provider_adapter": "mock", "api_token": "top-secret", "prompt": "ignore rules"},
    )
    event = exporter.events[0]
    assert event.attributes["api_token"] == "<redacted>"  # noqa: S105
    assert event.attributes["prompt"] == "<redacted>"
    with pytest.raises(AttributeError, match="bounded scalar"):
        telemetry.log(trace, "bad", {"details": {"nested": "data"}})
    with pytest.raises(AttributeError, match="limit"):
        telemetry.log(trace, "bad", {f"key_{index}": index for index in range(65)})


def test_export_failure_never_escapes_and_is_visible_in_health() -> None:
    class BrokenExporter:
        def export(self, event: TelemetryEvent) -> None:
            raise RuntimeError("contains provider payload")

    telemetry = Telemetry(BrokenExporter(), clock=clock, trace_id_factory=lambda: "3" * 32)
    trace = telemetry.start_trace("runtime.run")
    telemetry.log(trace, "still.running")
    assert telemetry.health().export_failures == 2
    assert telemetry.health().last_failure == "telemetry export failed"


def test_invalid_names_ids_values_and_duplicate_end_fail_safely() -> None:
    telemetry = Telemetry(InMemoryExporter(), clock=clock, trace_id_factory=lambda: "4" * 32)
    with pytest.raises(AttributeError, match="operation"):
        telemetry.start_trace("bad operation")
    trace = telemetry.start_trace("runtime.run")
    with pytest.raises(AttributeError, match="finite"):
        telemetry.metric("runtime.cost", float("nan"), trace=trace)
    telemetry.end_trace(trace, outcome="PASS")
    with pytest.raises(AttributeError, match="already ended"):
        telemetry.end_trace(trace, outcome="PASS")


def test_event_is_immutable_and_canonical() -> None:
    exporter = InMemoryExporter()
    telemetry = Telemetry(exporter, clock=clock, trace_id_factory=lambda: "5" * 32)
    telemetry.metric("queue.latency_ms", 4.5, {"state": "READY"})
    event = exporter.events[0]
    assert event.canonical()["attributes"] == {"state": "READY", "value": 4.5}
    with pytest.raises(TypeError):
        event.attributes["state"] = "FAILED"  # type: ignore[index]
