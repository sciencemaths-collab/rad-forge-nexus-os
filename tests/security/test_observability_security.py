from datetime import UTC, datetime

from nexus_os.observability import InMemoryExporter, Telemetry


def test_credential_canaries_never_reach_exporter() -> None:
    exporter = InMemoryExporter()
    telemetry = Telemetry(
        exporter,
        clock=lambda: datetime(2026, 8, 12, tzinfo=UTC),
        trace_id_factory=lambda: "a" * 32,
        exact_secrets=frozenset({"canary-value"}),
    )
    trace = telemetry.start_trace(
        "provider.call",
        {
            "authorization": "Bearer canary-value",
            "provider_metadata": "canary-value",
            "raw_user_data": "private",
            "artifact_digest": "sha256:" + "1" * 64,
        },
    )
    serialized = str(exporter.events[0].canonical())
    assert "canary-value" not in serialized
    assert "private" not in serialized
    assert exporter.events[0].attributes["artifact_digest"].startswith("sha256:")
    telemetry.end_trace(trace, outcome="PASS")
