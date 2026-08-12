import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from nexus_os.domain import RunId, TaskId, TraceId
from nexus_os.evidence import (
    GENESIS,
    EvidenceKind,
    EvidenceLedger,
    EvidenceOutcome,
    EvidenceRecord,
)


def record() -> EvidenceRecord:
    digest = "sha256:" + "1" * 64
    return EvidenceRecord(
        UUID("00000000-0000-4000-8000-000000000001"), 1,
        datetime(2026, 8, 12, 12, tzinfo=UTC), "project",
        RunId.parse("00000000-0000-4000-8000-000000000010"), TaskId("task_1"),
        "pytest", "nexus-os", EvidenceKind.SECURITY_TEST, EvidenceOutcome.PASS,
        "M-SECURITY-001", digest, digest, TraceId("1" * 32), GENESIS,
    )


def test_database_blocks_update_and_delete(tmp_path: Path) -> None:
    path = tmp_path / "evidence.db"
    ledger = EvidenceLedger(path)
    ledger.append(record(), expected_head=GENESIS)
    connection = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute("UPDATE evidence SET actor = 'attacker'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute("DELETE FROM evidence")
    connection.close()
    ledger.close()


def test_record_rejects_secret_payload_fields() -> None:
    assert set(record().to_dict()) == {
        "schema_version", "evidence_id", "timestamp", "project_id", "run_id",
        "task_id", "actor", "producer", "kind", "outcome", "test_id", "input_digest",
        "output_digest", "trace_id", "previous_record_hash", "record_hash",
    }
