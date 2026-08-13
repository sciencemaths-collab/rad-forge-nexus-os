"""Digest-bound runtime outcome evidence and Agent acceptance verification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from nexus_os.agent_store import AgentSessionStore, AgentState
from nexus_os.domain import RunState, TaskDefinition, TaskStatus, TraceId
from nexus_os.evidence import (
    GENESIS,
    EvidenceKind,
    EvidenceLedger,
    EvidenceOutcome,
    EvidenceRecord,
)
from nexus_os.runtime import RuntimeSnapshot
from nexus_os.tools import ToolResult


class RuntimeEvidenceError(ValueError):
    """Safe outcome evidence or acceptance verification failure."""


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    acceptance_id: str
    verification_method: str
    passed: bool
    environment: str
    output_digest: str


class AcceptanceVerifier(Protocol):
    def verify(
        self,
        criterion: Mapping[str, Any],
        snapshot: RuntimeSnapshot,
        records: tuple[EvidenceRecord, ...],
    ) -> AcceptanceResult: ...


class RuntimeEvidenceWriter:
    def __init__(self, ledger: EvidenceLedger) -> None:
        self._ledger = ledger

    def task_success(
        self,
        snapshot: RuntimeSnapshot,
        task: TaskDefinition,
        result: ToolResult,
        *,
        actor: str,
        trace_id: TraceId,
        now: datetime,
    ) -> EvidenceRecord:
        return self._append(
            snapshot,
            task,
            EvidenceKind.RUNTIME_EVENT,
            EvidenceOutcome.PASS,
            f"task:{task.task_id}",
            _digest(task.canonical_dict()),
            _digest(dict(result.output)),
            actor,
            trace_id,
            now,
        )

    def acceptance(
        self,
        snapshot: RuntimeSnapshot,
        criterion: Mapping[str, Any],
        result: AcceptanceResult,
        *,
        actor: str,
        trace_id: TraceId,
        now: datetime,
    ) -> EvidenceRecord:
        if (
            result.acceptance_id != criterion.get("acceptance_id")
            or result.verification_method != criterion.get("verification_method")
            or not result.environment.strip()
        ):
            raise RuntimeEvidenceError("acceptance verifier result binding is invalid")
        return self._append(
            snapshot,
            None,
            EvidenceKind.TEST,
            EvidenceOutcome.PASS if result.passed else EvidenceOutcome.FAIL,
            result.acceptance_id,
            _digest({"criterion": dict(criterion), "environment": result.environment}),
            result.output_digest,
            actor,
            trace_id,
            now,
        )

    def _append(
        self,
        snapshot: RuntimeSnapshot,
        task: TaskDefinition | None,
        kind: EvidenceKind,
        outcome: EvidenceOutcome,
        test_id: str,
        input_digest: str,
        output_digest: str,
        actor: str,
        trace_id: TraceId,
        now: datetime,
    ) -> EvidenceRecord:
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise RuntimeEvidenceError("evidence timestamp must be timezone-aware UTC")
        records = self._ledger.records(snapshot.graph.graph.project_id, snapshot.run_id)
        identity = uuid5(
            NAMESPACE_URL,
            f"nexus:evidence:{snapshot.run_id}:{test_id}:{input_digest}:{output_digest}",
        )
        for existing in records:
            if existing.evidence_id == identity:
                if (
                    existing.input_digest != input_digest
                    or existing.output_digest != output_digest
                    or existing.outcome is not outcome
                ):
                    raise RuntimeEvidenceError("evidence identity conflicts with stored record")
                return existing
        head = GENESIS if not records else records[-1].record_hash
        record = EvidenceRecord(
            identity,
            len(records) + 1,
            now,
            snapshot.graph.graph.project_id,
            snapshot.run_id,
            None if task is None else task.task_id,
            actor,
            "nexus.runtime-evidence/1.0",
            kind,
            outcome,
            test_id,
            input_digest,
            output_digest,
            trace_id,
            head,
        )
        return self._ledger.append(record, expected_head=head)


class RuntimeTaskEvidenceVerifier:
    """Verify a criterion only from complete, hash-valid task evidence bound to it."""

    method = "runtime_task_evidence"

    def verify(
        self,
        criterion: Mapping[str, Any],
        snapshot: RuntimeSnapshot,
        records: tuple[EvidenceRecord, ...],
    ) -> AcceptanceResult:
        acceptance_id = str(criterion.get("acceptance_id", ""))
        relevant_tasks = {
            task.task_id
            for task in snapshot.graph.graph.tasks
            if acceptance_id in task.acceptance_ids
        }
        passing = {
            record.task_id
            for record in records
            if record.kind is EvidenceKind.RUNTIME_EVENT
            and record.outcome is EvidenceOutcome.PASS
            and record.task_id is not None
        }
        bound_records = tuple(
            record.record_hash for record in records if record.task_id in relevant_tasks
        )
        return AcceptanceResult(
            acceptance_id,
            self.method,
            bool(relevant_tasks) and relevant_tasks <= passing,
            "local-governed-runtime",
            _digest({"acceptance_id": acceptance_id, "records": bound_records}),
        )


class AgentCompletionVerifier:
    def __init__(
        self,
        *,
        sessions: AgentSessionStore,
        ledger: EvidenceLedger,
        writer: RuntimeEvidenceWriter,
        verifiers: Mapping[str, AcceptanceVerifier],
    ) -> None:
        self._sessions = sessions
        self._ledger = ledger
        self._writer = writer
        self._verifiers = dict(verifiers)

    def verify(
        self,
        session_id: UUID,
        snapshot: RuntimeSnapshot,
        *,
        start_event_id: UUID,
        completion_event_id: UUID,
        actor_id: str,
        trace_id: TraceId,
        now: datetime,
        expected_sequence: int,
    ) -> bool:
        session = self._sessions.get(session_id)
        candidate = self._sessions.get_candidate(session_id)
        if (
            session.state not in {AgentState.RUNNING, AgentState.VERIFYING}
            or session.run_id != snapshot.run_id.value
            or session.approved_candidate_digest != candidate.digest
            or snapshot.run_state is not RunState.SUCCEEDED
            or any(status is not TaskStatus.SUCCEEDED for status in snapshot.task_states.values())
        ):
            raise RuntimeEvidenceError("runtime is not eligible for completion verification")
        records = self._ledger.records(session.project_id, snapshot.run_id)
        passed_tasks = {
            record.task_id
            for record in records
            if record.kind is EvidenceKind.RUNTIME_EVENT
            and record.outcome is EvidenceOutcome.PASS
            and record.task_id is not None
        }
        if passed_tasks != set(snapshot.task_states):
            raise RuntimeEvidenceError("task outcome evidence is incomplete")
        self._ledger.verify(session.project_id, snapshot.run_id)
        verifying = (
            self._sessions.start_verification(
                session_id,
                event_id=start_event_id,
                actor_id=actor_id,
                occurred_at=now,
                expected_sequence=expected_sequence,
            )
            if session.state is AgentState.RUNNING
            else session
        )
        all_passed = True
        for criterion in candidate.document["acceptance_criteria"]:
            method = str(criterion["verification_method"])
            verifier = self._verifiers.get(method)
            if verifier is None:
                raise RuntimeEvidenceError("approved acceptance verifier is not registered")
            result = verifier.verify(criterion, snapshot, records)
            self._writer.acceptance(
                snapshot, criterion, result, actor=actor_id, trace_id=trace_id, now=now
            )
            all_passed = all_passed and result.passed
        final_records = self._ledger.records(session.project_id, snapshot.run_id)
        verification = self._ledger.verify(session.project_id, snapshot.run_id)
        expected_ids = {item["acceptance_id"] for item in candidate.document["acceptance_criteria"]}
        passing_ids = {
            record.test_id
            for record in final_records
            if record.kind is EvidenceKind.TEST and record.outcome is EvidenceOutcome.PASS
        }
        all_passed = (
            all_passed
            and expected_ids <= passing_ids
            and verification.record_count == len(final_records)
        )
        self._sessions.complete_verification(
            session_id,
            event_id=completion_event_id,
            actor_id=actor_id,
            occurred_at=now,
            expected_sequence=len(verifying.events),
            passed=all_passed,
        )
        return all_passed


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()
