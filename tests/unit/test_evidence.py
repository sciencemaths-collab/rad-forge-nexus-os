from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from nexus_os.domain import RunId, TaskId, TraceId
from nexus_os.evidence import (
    GENESIS,
    EvidenceError,
    EvidenceKind,
    EvidenceOutcome,
    EvidenceRecord,
    verify_chain,
)

DIGEST = "sha256:" + "1" * 64
RUN = RunId.parse("00000000-0000-4000-8000-000000000010")


def record(sequence: int = 1, previous: str = GENESIS) -> EvidenceRecord:
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
        "M-UNIT-001",
        DIGEST,
        DIGEST,
        TraceId("1" * 32),
        previous,
    )


def test_seal_and_verify_are_deterministic() -> None:
    first = record().seal()
    second = record(2, first.record_hash).seal()
    assert first.record_hash == record().computed_hash()
    assert verify_chain((first, second)).head_hash == second.record_hash


@pytest.mark.parametrize("change", ["mutation", "deletion", "reordering", "broken_link"])
def test_verifier_detects_chain_attacks(change: str) -> None:
    first = record().seal()
    second = record(2, first.record_hash).seal()
    records = (first, second)
    if change == "mutation":
        records = (replace(first, actor="attacker"), second)
    elif change == "deletion":
        records = (second,)
    elif change == "reordering":
        records = (second, first)
    else:
        records = (first, replace(second, previous_record_hash=DIGEST))
    with pytest.raises(EvidenceError):
        verify_chain(records)


def test_unsealed_and_empty_chains_are_rejected() -> None:
    with pytest.raises(EvidenceError, match="empty"):
        verify_chain(())
    with pytest.raises(EvidenceError, match="hash"):
        verify_chain((record(),))


def test_trusted_anchor_detects_tail_deletion() -> None:
    first = record().seal()
    second = record(2, first.record_hash).seal()
    with pytest.raises(EvidenceError, match="count"):
        verify_chain((first,), expected_count=2, expected_head=second.record_hash)
