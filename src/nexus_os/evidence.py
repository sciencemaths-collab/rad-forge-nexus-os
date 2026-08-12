"""Durable, append-only, tamper-evident evidence records."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from nexus_os.domain import RunId, TaskId, TraceId

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
GENESIS = "GENESIS"


class EvidenceError(ValueError):
    """Safe evidence validation, persistence, or verification failure."""


class EvidenceKind(StrEnum):
    SPECIFICATION = "SPECIFICATION"
    TEST = "TEST"
    SECURITY_TEST = "SECURITY_TEST"
    BENCHMARK = "BENCHMARK"
    ARTIFACT = "ARTIFACT"
    APPROVAL = "APPROVAL"
    QUALIFICATION = "QUALIFICATION"
    RUNTIME_EVENT = "RUNTIME_EVENT"


class EvidenceOutcome(StrEnum):
    PASS = "PASS"  # noqa: S105 - test outcome, not a credential
    FAIL = "FAIL"
    ERROR = "ERROR"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: UUID
    sequence: int
    timestamp: datetime
    project_id: str
    run_id: RunId
    task_id: TaskId | None
    actor: str
    producer: str
    kind: EvidenceKind
    outcome: EvidenceOutcome
    test_id: str | None
    input_digest: str
    output_digest: str
    trace_id: TraceId
    previous_record_hash: str
    record_hash: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, UUID):
            raise EvidenceError("evidence_id must be a UUID")
        invalid_sequence = (
            not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence < 1
        )
        if invalid_sequence:
            raise EvidenceError("sequence must be a positive integer")
        _utc(self.timestamp)
        _bounded(self.project_id, "project_id", 256)
        _bounded(self.actor, "actor", 256)
        _bounded(self.producer, "producer", 256)
        if self.test_id is not None:
            _bounded(self.test_id, "test_id", 256)
        _digest(self.input_digest, "input_digest")
        _digest(self.output_digest, "output_digest")
        if self.previous_record_hash != GENESIS:
            _digest(self.previous_record_hash, "previous_record_hash")
        if self.record_hash:
            _digest(self.record_hash, "record_hash")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "evidence_id": str(self.evidence_id),
            "timestamp": self.timestamp.isoformat(),
            "project_id": self.project_id,
            "run_id": str(self.run_id),
            "task_id": None if self.task_id is None else str(self.task_id),
            "actor": self.actor,
            "producer": self.producer,
            "kind": self.kind.value,
            "outcome": self.outcome.value,
            "test_id": self.test_id,
            "input_digest": self.input_digest,
            "output_digest": self.output_digest,
            "trace_id": str(self.trace_id),
            "previous_record_hash": self.previous_record_hash,
        }

    def computed_hash(self) -> str:
        raw = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        return f"sha256:{hashlib.sha256(raw).hexdigest()}"

    def seal(self) -> EvidenceRecord:
        if self.record_hash:
            raise EvidenceError("record is already sealed")
        return replace(self, record_hash=self.computed_hash())

    def to_dict(self) -> dict[str, Any]:
        return {**self.canonical_payload(), "record_hash": self.record_hash}


@dataclass(frozen=True, slots=True)
class VerificationResult:
    record_count: int
    head_hash: str


class EvidenceLedger:
    """SQLite hash-chain ledger with atomic expected-head appends."""

    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL,
            timestamp TEXT NOT NULL, project_id TEXT NOT NULL, run_id TEXT NOT NULL,
            task_id TEXT, actor TEXT NOT NULL, producer TEXT NOT NULL, kind TEXT NOT NULL,
            outcome TEXT NOT NULL, test_id TEXT, input_digest TEXT NOT NULL,
            output_digest TEXT NOT NULL, trace_id TEXT NOT NULL,
            previous_record_hash TEXT NOT NULL, record_hash TEXT NOT NULL,
            UNIQUE(project_id, run_id, sequence), UNIQUE(project_id, run_id, record_hash))"""
        )
        self._connection.execute(
            """CREATE TRIGGER IF NOT EXISTS evidence_no_update BEFORE UPDATE ON evidence
            BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END"""
        )
        self._connection.execute(
            """CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON evidence
            BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END"""
        )

    def close(self) -> None:
        self._connection.close()

    def append(self, record: EvidenceRecord, *, expected_head: str) -> EvidenceRecord:
        if record.record_hash:
            raise EvidenceError("ledger accepts only unsealed records")
        if expected_head != GENESIS:
            _digest(expected_head, "expected_head")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            rows = self._connection.execute(
                """SELECT sequence, record_hash FROM evidence
                WHERE project_id = ? AND run_id = ? ORDER BY sequence DESC LIMIT 1""",
                (record.project_id, str(record.run_id)),
            ).fetchone()
            actual_head = GENESIS if rows is None else str(rows[1])
            next_sequence = 1 if rows is None else int(rows[0]) + 1
            if expected_head != actual_head:
                raise EvidenceError("evidence head changed")
            if record.previous_record_hash != actual_head or record.sequence != next_sequence:
                raise EvidenceError("record does not extend the current evidence chain")
            sealed = record.seal()
            values = {**sealed.to_dict(), "sequence": sealed.sequence}
            self._connection.execute(
                """INSERT INTO evidence VALUES
                (:evidence_id, :sequence, :timestamp, :project_id, :run_id, :task_id,
                :actor, :producer, :kind, :outcome, :test_id, :input_digest,
                :output_digest, :trace_id, :previous_record_hash, :record_hash)""",
                values,
            )
            self._connection.execute("COMMIT")
            return sealed
        except sqlite3.IntegrityError as exc:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise EvidenceError("duplicate or conflicting evidence record") from exc
        except Exception:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise

    def records(self, project_id: str, run_id: RunId) -> tuple[EvidenceRecord, ...]:
        rows = self._connection.execute(
            "SELECT * FROM evidence WHERE project_id = ? AND run_id = ? ORDER BY sequence",
            (project_id, str(run_id)),
        ).fetchall()
        return tuple(_from_row(row) for row in rows)

    def verify(self, project_id: str, run_id: RunId) -> VerificationResult:
        return verify_chain(self.records(project_id, run_id))


def verify_chain(
    records: tuple[EvidenceRecord, ...],
    *,
    expected_count: int | None = None,
    expected_head: str | None = None,
) -> VerificationResult:
    if not records:
        raise EvidenceError("evidence chain is empty")
    if expected_count is not None and len(records) != expected_count:
        raise EvidenceError("evidence chain record count does not match trusted anchor")
    if expected_head is not None:
        _digest(expected_head, "expected_head")
    expected_previous = GENESIS
    seen: set[UUID] = set()
    scope = (records[0].project_id, records[0].run_id)
    for expected_sequence, record in enumerate(records, start=1):
        if (record.project_id, record.run_id) != scope:
            raise EvidenceError("evidence chain contains mixed scopes")
        if record.evidence_id in seen:
            raise EvidenceError("evidence chain contains duplicate identifiers")
        if record.sequence != expected_sequence:
            raise EvidenceError("evidence chain has a sequence gap or reordering")
        if record.previous_record_hash != expected_previous:
            raise EvidenceError("evidence chain link is broken")
        if record.record_hash != record.computed_hash():
            raise EvidenceError("evidence record hash is invalid")
        seen.add(record.evidence_id)
        expected_previous = record.record_hash
    if expected_head is not None and expected_previous != expected_head:
        raise EvidenceError("evidence chain head does not match trusted anchor")
    return VerificationResult(len(records), expected_previous)


def _from_row(row: tuple[object, ...]) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=UUID(str(row[0])), sequence=int(str(row[1])),
        timestamp=datetime.fromisoformat(str(row[2])), project_id=str(row[3]),
        run_id=RunId.parse(row[4]), task_id=None if row[5] is None else TaskId(str(row[5])),
        actor=str(row[6]), producer=str(row[7]), kind=EvidenceKind(str(row[8])),
        outcome=EvidenceOutcome(str(row[9])), test_id=None if row[10] is None else str(row[10]),
        input_digest=str(row[11]), output_digest=str(row[12]), trace_id=TraceId(str(row[13])),
        previous_record_hash=str(row[14]), record_hash=str(row[15]),
    )


def _bounded(value: object, name: str, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise EvidenceError(f"{name} must be a non-empty bounded string")


def _digest(value: object, name: str) -> None:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise EvidenceError(f"{name} must be a sha256 digest")


def _utc(value: datetime) -> None:
    invalid = (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    )
    if invalid:
        raise EvidenceError("timestamp must be timezone-aware UTC")
