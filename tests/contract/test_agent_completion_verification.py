from datetime import UTC, datetime

import pytest

from nexus_os.agent_store import AgentSessionStore, CandidateSpecification, ReviewPrincipal
from nexus_os.domain import RunId, TaskId, TaskStatus, TraceId
from nexus_os.evidence import EvidenceLedger
from nexus_os.graph import compile_task_graph, validate_task_graph
from nexus_os.runtime import RuntimeOrchestrator
from nexus_os.runtime_evidence import (
    AcceptanceResult,
    AgentCompletionVerifier,
    RuntimeEvidenceError,
    RuntimeEvidenceWriter,
    RuntimeTaskEvidenceVerifier,
)
from nexus_os.stores import SQLiteCheckpointStore
from nexus_os.tools import ToolResult
from tests.unit.test_agent_store import SESSION_ID, candidate, created, uid

NOW = datetime(2026, 8, 13, 22, tzinfo=UTC)
TRACE = TraceId("fedcba0987654321fedcba0987654321")
RUN = RunId.parse("84000000-0000-4000-8000-000000000001")


def _graph():
    return validate_task_graph(
        compile_task_graph(
            {
                "schema_version": "1.0",
                "graph_id": "84000000-0000-4000-8000-000000000002",
                "project_id": "reference_agent",
                "tasks": [
                    {
                        "task_id": "evidence_task",
                        "kind": "nexus.test",
                        "depends_on": [],
                        "effect": "READ_ONLY",
                        "timeout_seconds": 30,
                        "retry": {"max_attempts": 1, "backoff_seconds": 0},
                        "input": {"value": "approved"},
                        "acceptance_ids": ["AC-BUILD"],
                    }
                ],
            }
        )
    )


def _running(store: AgentSessionStore):
    created(store)
    spec = CandidateSpecification.parse(candidate())
    store.save_candidate(
        spec, event_id=uid(11), actor_id="qualified-agent", occurred_at=NOW, expected_sequence=1
    )
    store.start_review(
        SESSION_ID, event_id=uid(12), actor_id="agent-service", occurred_at=NOW, expected_sequence=2
    )
    store.approve(
        SESSION_ID,
        event_id=uid(13),
        candidate_digest=spec.digest,
        principal=ReviewPrincipal("owner-reviewer", True, True),
        occurred_at=NOW,
        expected_sequence=3,
    )
    return store.start_run(
        SESSION_ID,
        event_id=uid(14),
        run_id=RUN.value,
        candidate_digest=spec.digest,
        actor_id="handoff-service",
        occurred_at=NOW,
        expected_sequence=4,
    )


class Verifier:
    def __init__(self, passed=True):
        self.passed = passed

    def verify(self, criterion, snapshot, records):
        return AcceptanceResult(
            criterion["acceptance_id"],
            criterion["verification_method"],
            self.passed,
            "test:locked",
            "sha256:" + "2" * 64,
        )


def _succeeded(tmp_path):
    runtime = RuntimeOrchestrator(SQLiteCheckpointStore(tmp_path / "runtime.db"))
    graph = _graph()
    snapshot = runtime.create(run_id=RUN, graph=graph, trace_id=TRACE, now=NOW)
    running = runtime.start_task(snapshot, TaskId("evidence_task"), trace_id=TRACE, now=NOW)
    return runtime.complete_task(
        running, TaskId("evidence_task"), TaskStatus.SUCCEEDED, trace_id=TRACE, now=NOW
    ), graph.graph.tasks[0]


def test_agent_completes_only_after_task_and_acceptance_evidence_verify(tmp_path) -> None:
    sessions = AgentSessionStore(tmp_path / "agent.db")
    _running(sessions)
    snapshot, task = _succeeded(tmp_path)
    ledger = EvidenceLedger(tmp_path / "evidence.db")
    writer = RuntimeEvidenceWriter(ledger)
    writer.task_success(
        snapshot,
        task,
        ToolResult("nexus.test", {"ok": True}, "sha256:" + "1" * 64, False),
        actor="runtime",
        trace_id=TRACE,
        now=NOW,
    )
    service = AgentCompletionVerifier(
        sessions=sessions,
        ledger=ledger,
        writer=writer,
        verifiers={"Run the declared build gate.": Verifier()},
    )
    assert service.verify(
        SESSION_ID,
        snapshot,
        start_event_id=uid(15),
        completion_event_id=uid(16),
        actor_id="verification-service",
        trace_id=TRACE,
        now=NOW,
        expected_sequence=5,
    )
    assert sessions.get(SESSION_ID).state.value == "COMPLETED"
    assert ledger.verify("reference_agent", RUN).record_count == 2


def test_missing_task_evidence_cannot_enter_verification_or_complete(tmp_path) -> None:
    sessions = AgentSessionStore(tmp_path / "agent.db")
    _running(sessions)
    snapshot, _ = _succeeded(tmp_path)
    ledger = EvidenceLedger(tmp_path / "evidence.db")
    service = AgentCompletionVerifier(
        sessions=sessions,
        ledger=ledger,
        writer=RuntimeEvidenceWriter(ledger),
        verifiers={"Run the declared build gate.": Verifier()},
    )
    with pytest.raises(RuntimeEvidenceError, match="incomplete"):
        service.verify(
            SESSION_ID,
            snapshot,
            start_event_id=uid(15),
            completion_event_id=uid(16),
            actor_id="verification-service",
            trace_id=TRACE,
            now=NOW,
            expected_sequence=5,
        )
    assert sessions.get(SESSION_ID).state.value == "RUNNING"


def test_failed_acceptance_evidence_finishes_agent_as_failed(tmp_path) -> None:
    sessions = AgentSessionStore(tmp_path / "agent.db")
    _running(sessions)
    snapshot, task = _succeeded(tmp_path)
    ledger = EvidenceLedger(tmp_path / "evidence.db")
    writer = RuntimeEvidenceWriter(ledger)
    writer.task_success(
        snapshot,
        task,
        ToolResult("nexus.test", {"ok": True}, "sha256:" + "1" * 64, False),
        actor="runtime",
        trace_id=TRACE,
        now=NOW,
    )
    service = AgentCompletionVerifier(
        sessions=sessions,
        ledger=ledger,
        writer=writer,
        verifiers={"Run the declared build gate.": Verifier(False)},
    )
    assert not service.verify(
        SESSION_ID,
        snapshot,
        start_event_id=uid(15),
        completion_event_id=uid(16),
        actor_id="verification-service",
        trace_id=TRACE,
        now=NOW,
        expected_sequence=5,
    )
    assert sessions.get(SESSION_ID).state.value == "FAILED"


def test_runtime_task_verifier_uses_only_digest_bound_task_evidence(tmp_path) -> None:
    snapshot, task = _succeeded(tmp_path)
    ledger = EvidenceLedger(tmp_path / "evidence.db")
    writer = RuntimeEvidenceWriter(ledger)
    criterion = {
        "acceptance_id": "AC-BUILD",
        "statement": "Build evidence exists.",
        "verification_method": RuntimeTaskEvidenceVerifier.method,
    }
    verifier = RuntimeTaskEvidenceVerifier()
    missing = verifier.verify(criterion, snapshot, ())
    assert not missing.passed

    writer.task_success(
        snapshot,
        task,
        ToolResult("nexus.test", {"ok": True}, "sha256:" + "1" * 64, False),
        actor="runtime",
        trace_id=TRACE,
        now=NOW,
    )
    records = ledger.records("reference_agent", RUN)
    verified = verifier.verify(criterion, snapshot, records)
    assert verified.passed
    assert verified.output_digest.startswith("sha256:")
