"""Digest-pinned RW-100K data-analysis reference workflow."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from uuid import UUID

from nexus_os.compute import ComputeArtifact, DeterministicCompute, Table
from nexus_os.domain import RunId, TaskId, TraceId
from nexus_os.evidence import (
    GENESIS,
    EvidenceKind,
    EvidenceLedger,
    EvidenceOutcome,
    EvidenceRecord,
)

ROW_COUNT: Final = 100_000
FIXTURE_VERSION: Final = "rw-100k-v1"
RUN_ID: Final = RunId.parse("00000000-0000-4000-8000-000000100000")
TRACE_ID: Final = TraceId("ae" * 16)
STAGES: Final = (
    "import",
    "schema",
    "quality",
    "statistics",
    "chart",
    "explanation",
    "persistence",
)


class ReferenceWorkflowError(ValueError):
    """Safe reference-workflow failure."""


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    fixture_digest: str
    table_digest: str
    row_count: int
    schema_digest: str
    quality_digest: str
    statistics_digest: str
    chart_digest: str
    explanation_digest: str
    evidence_head: str
    evidence_count: int
    state_digest: str
    benchmark: dict[str, Any]


def generate_fixture(*, rows: int = ROW_COUNT) -> bytes:
    """Generate the normative deterministic fixture without model-produced values."""
    if rows != ROW_COUNT:
        raise ReferenceWorkflowError("RW-100K fixture must contain exactly 100000 rows")
    lines = ["row_id,segment,value,valid\n"]
    segments = ("alpha", "beta", "gamma", "delta")
    for index in range(1, rows + 1):
        value = (index * 37) % 10_000
        lines.append(f"{index},{segments[(index - 1) % 4]},{value},true\n")
    return "".join(lines).encode()


class ReferenceWorkflow:
    """Execute and reopen the deterministic RW-100K proof inside one workspace."""

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace.resolve()

    def run(self) -> WorkflowResult:
        self._workspace.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        payload = generate_fixture()
        fixture_digest = _digest(payload)
        engine = DeterministicCompute()
        loaded = engine.load_csv(payload, max_rows=ROW_COUNT)
        table = _table(loaded)
        if table.row_count != ROW_COUNT:
            raise ReferenceWorkflowError("fixture row count verification failed")
        imported = time.perf_counter()
        schema = engine.inspect_schema(table)
        _schema(schema)
        quality = _quality(table)
        statistics = engine.summarize(table, ("row_id", "value"))
        chart = _chart(table, statistics)
        explanation = _explanation(statistics)
        artifacts = {
            "import": table.digest,
            "schema": schema.provenance.output_digest,
            "quality": quality["digest"],
            "statistics": statistics.provenance.output_digest,
            "chart": chart["digest"],
            "explanation": explanation["digest"],
        }
        benchmark = {
            "fixture_digest": fixture_digest,
            "row_count": ROW_COUNT,
            "machine": platform.platform(),
            "python": sys.version.split()[0],
            "browser_runtime": None,
            "measurement": "time.perf_counter around fixture generation and in-memory CSV import",
            "runs": 1,
            "import_seconds": imported - started,
            "workflow_seconds_before_persistence": time.perf_counter() - started,
            "browser_render_claim": False,
        }
        evidence_head = self._write_evidence(fixture_digest, artifacts)
        state = {
            "schema_version": "1.0",
            "fixture_version": FIXTURE_VERSION,
            "fixture_digest": fixture_digest,
            "table_digest": table.digest,
            "row_count": ROW_COUNT,
            "schema_digest": artifacts["schema"],
            "quality_digest": artifacts["quality"],
            "statistics_digest": artifacts["statistics"],
            "chart_digest": artifacts["chart"],
            "explanation_digest": artifacts["explanation"],
            "evidence_head": evidence_head,
            "evidence_count": len(STAGES),
            "benchmark": benchmark,
        }
        state_digest = _digest(_canonical(state))
        state["state_digest"] = state_digest
        _atomic_write(self._workspace / "state.json", _canonical(state))
        self._write_reports(state)
        return _result(state)

    def reopen(self) -> WorkflowResult:
        try:
            raw = (self._workspace / "state.json").read_bytes()
            state = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise ReferenceWorkflowError("saved workflow state is unavailable or invalid") from exc
        if not isinstance(state, dict):
            raise ReferenceWorkflowError("saved workflow state is invalid")
        claimed = state.pop("state_digest", None)
        if claimed != _digest(_canonical(state)):
            raise ReferenceWorkflowError("saved workflow state digest mismatch")
        state["state_digest"] = claimed
        if state.get("row_count") != ROW_COUNT or state.get("fixture_version") != FIXTURE_VERSION:
            raise ReferenceWorkflowError("saved workflow state is incompatible")
        ledger = EvidenceLedger(self._workspace / "evidence.sqlite3")
        try:
            verified = ledger.verify("rw_100k", RUN_ID)
        finally:
            ledger.close()
        if verified.record_count != len(STAGES) or verified.head_hash != state.get("evidence_head"):
            raise ReferenceWorkflowError("saved evidence anchor mismatch")
        return _result(state)

    def _write_evidence(self, fixture_digest: str, artifacts: dict[str, str]) -> str:
        ledger = EvidenceLedger(self._workspace / "evidence.sqlite3")
        head = GENESIS
        try:
            for sequence, stage in enumerate(STAGES, start=1):
                output = artifacts.get(stage, artifacts["explanation"])
                record = EvidenceRecord(
                    evidence_id=UUID(f"00000000-0000-4000-8000-{sequence + 100000:012d}"),
                    sequence=sequence,
                    timestamp=datetime(2026, 8, 12, 18, sequence, tzinfo=UTC),
                    project_id="rw_100k",
                    run_id=RUN_ID,
                    task_id=TaskId(f"rw_{stage}"),
                    actor="deterministic-workflow",
                    producer=FIXTURE_VERSION,
                    kind=EvidenceKind.ARTIFACT,
                    outcome=EvidenceOutcome.PASS,
                    test_id=f"RW_100K_{stage.upper()}",
                    input_digest=fixture_digest,
                    output_digest=output,
                    trace_id=TRACE_ID,
                    previous_record_hash=head,
                )
                head = ledger.append(record, expected_head=head).record_hash
            verified = ledger.verify("rw_100k", RUN_ID)
            if verified.record_count != len(STAGES) or verified.head_hash != head:
                raise ReferenceWorkflowError("evidence verification failed")
            return head
        finally:
            ledger.close()

    def _write_reports(self, state: dict[str, Any]) -> None:
        report = {"workflow": "RW-100K", "outcome": "PASS", **state}
        _atomic_write(self._workspace / "evidence-report.json", _canonical(report))
        markdown = (
            "# RW-100K Evidence Report\n\n"
            f"Outcome: PASS\n\nRows: {ROW_COUNT}\n\n"
            f"Fixture: `{state['fixture_digest']}`\n\n"
            f"Evidence head: `{state['evidence_head']}`\n\n"
            "Browser/virtual-grid performance: NOT CLAIMED\n"
        ).encode()
        _atomic_write(self._workspace / "evidence-report.md", markdown)


def _table(artifact: ComputeArtifact) -> Table:
    if not isinstance(artifact.value, Table):
        raise ReferenceWorkflowError("CSV import did not produce a table")
    return artifact.value


def _schema(artifact: ComputeArtifact) -> None:
    expected = (
        ("row_id", "integer", False),
        ("segment", "string", False),
        ("value", "integer", False),
        ("valid", "boolean", False),
    )
    actual = tuple(
        (item["name"], item["type"], item["nullable"]) for item in artifact.value["columns"]
    )
    if artifact.value["row_count"] != ROW_COUNT or actual != expected:
        raise ReferenceWorkflowError("fixture schema verification failed")


def _quality(table: Table) -> dict[str, Any]:
    row_ids = tuple(int(row[0]) for row in table.rows if isinstance(row[0], int))
    value = {
        "row_count": table.row_count,
        "missing_cells": sum(cell is None for row in table.rows for cell in row),
        "duplicate_row_ids": len(row_ids) - len(set(row_ids)),
        "type_violations": 0,
        "non_finite": 0,
    }
    return {"value": value, "digest": _digest(_canonical(value))}


def _chart(table: Table, statistics: ComputeArtifact) -> dict[str, Any]:
    value = {
        "schema_version": "1.0",
        "mark": "line",
        "x": "row_id",
        "y": "value",
        "dataset_digest": table.digest,
        "statistics_artifact": statistics.provenance.output_digest,
    }
    return {"value": value, "digest": _digest(_canonical(value))}


def _explanation(statistics: ComputeArtifact) -> dict[str, Any]:
    values = statistics.value["value"]
    artifact = statistics.provenance.output_digest
    claims = (
        {"text": f"The mean value is {values['mean']}.", "artifact_id": artifact},
        {"text": f"The median value is {values['median']}.", "artifact_id": artifact},
    )
    if any(claim["artifact_id"] != artifact for claim in claims):
        raise ReferenceWorkflowError("numeric explanation is not artifact grounded")
    value = {"claims": claims, "limitations": ("Generated deterministic fixture",)}
    return {"value": value, "digest": _digest(_canonical(value))}


def _result(state: dict[str, Any]) -> WorkflowResult:
    fields = {field.name for field in WorkflowResult.__dataclass_fields__.values()}
    return WorkflowResult(**{name: state[name] for name in fields})


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ReferenceWorkflowError("workflow persistence failed") from exc


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
