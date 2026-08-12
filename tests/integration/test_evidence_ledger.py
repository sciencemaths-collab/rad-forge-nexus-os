from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from nexus_os.domain import RunId, TaskId, TraceId
from nexus_os.evidence import (
    GENESIS,
    EvidenceError,
    EvidenceKind,
    EvidenceLedger,
    EvidenceOutcome,
    EvidenceRecord,
)

RUN = RunId.parse("00000000-0000-4000-8000-000000000010")


def record(sequence: int = 1, previous: str = GENESIS) -> EvidenceRecord:
    digest = "sha256:" + "1" * 64
    return EvidenceRecord(
        UUID(f"00000000-0000-4000-8000-{sequence:012d}"),
        sequence,
        datetime(2026, 8, 12, 12, sequence, tzinfo=UTC),
        "project",
        RUN,
        TaskId("task_1"),
        "pytest",
        "nexus-os",
        EvidenceKind.TEST,
        EvidenceOutcome.PASS,
        "M-INTEGRATION-001",
        digest,
        digest,
        TraceId("1" * 32),
        previous,
    )


def test_append_restart_and_verify(tmp_path: Path) -> None:
    path = tmp_path / "evidence.db"
    ledger = EvidenceLedger(path)
    first = ledger.append(record(), expected_head=GENESIS)
    second = ledger.append(record(2, first.record_hash), expected_head=first.record_hash)
    ledger.close()

    reopened = EvidenceLedger(path)
    result = reopened.verify("project", RUN)
    assert result.record_count == 2
    assert result.head_hash == second.record_hash
    reopened.close()


def test_stale_writer_and_non_extending_append_are_rejected(tmp_path: Path) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence.db")
    first = ledger.append(record(), expected_head=GENESIS)
    with pytest.raises(EvidenceError, match="head changed"):
        ledger.append(record(2, first.record_hash), expected_head=GENESIS)
    with pytest.raises(EvidenceError, match="does not extend"):
        ledger.append(record(3, first.record_hash), expected_head=first.record_hash)
    ledger.close()
