from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from nexus_os.domain import RunId, TraceId
from nexus_os.evidence import GENESIS, EvidenceKind, EvidenceOutcome, EvidenceRecord
from nexus_os.qualification import (
    CapabilityState,
    QualificationError,
    QualificationRule,
    evaluate,
)


def evidence_record(sequence: int, kind: EvidenceKind, previous: str = GENESIS) -> EvidenceRecord:
    digest = "sha256:" + "1" * 64
    return EvidenceRecord(
        UUID(f"00000000-0000-4000-8000-{sequence:012d}"),
        sequence,
        datetime(2026, 8, 12, 12, sequence, tzinfo=UTC),
        "project",
        RunId.parse("00000000-0000-4000-8000-000000000010"),
        None,
        "pytest",
        "nexus-os",
        kind,
        EvidenceOutcome.PASS,
        f"N-{sequence}",
        digest,
        digest,
        TraceId("1" * 32),
        previous,
    )


def test_passing_required_evidence_qualifies() -> None:
    first = evidence_record(1, EvidenceKind.TEST).seal()
    second = evidence_record(2, EvidenceKind.SECURITY_TEST, first.record_hash).seal()
    rule = QualificationRule(
        "runtime.core", "1.0", frozenset({EvidenceKind.TEST, EvidenceKind.SECURITY_TEST}), 2
    )
    result = evaluate(
        rule,
        (first, second),
        evaluated_at=datetime(2026, 8, 12, 13, tzinfo=UTC),
        expected_head=second.record_hash,
    )
    assert result.state is CapabilityState.QUALIFIED
    assert len(result.evidence_ids) == 2


def test_missing_or_failed_evidence_cannot_promote() -> None:
    first = evidence_record(1, EvidenceKind.TEST).seal()
    failed = replace(
        evidence_record(2, EvidenceKind.SECURITY_TEST, first.record_hash),
        outcome=EvidenceOutcome.FAIL,
    ).seal()
    rule = QualificationRule(
        "runtime.core", "1.0", frozenset({EvidenceKind.TEST, EvidenceKind.SECURITY_TEST}), 2
    )
    result = evaluate(
        rule,
        (first, failed),
        evaluated_at=datetime(2026, 8, 12, 13, tzinfo=UTC),
        expected_head=failed.record_hash,
    )
    assert result.state is CapabilityState.UNKNOWN
    assert result.evidence_ids == ()


def test_broken_chain_and_production_target_are_rejected() -> None:
    item = evidence_record(1, EvidenceKind.TEST).seal()
    rule = QualificationRule("runtime.core", "1.0", frozenset({EvidenceKind.TEST}), 1)
    with pytest.raises(QualificationError, match="integrity"):
        evaluate(rule, (item,), evaluated_at=datetime.now(UTC), expected_head="sha256:" + "2" * 64)
    with pytest.raises(QualificationError, match="production"):
        QualificationRule(
            "runtime.core", "1.0", frozenset({EvidenceKind.TEST}), 1, CapabilityState.PRODUCTION
        )


def test_qualification_expiry_is_derived_from_rule() -> None:
    item = evidence_record(1, EvidenceKind.TEST).seal()
    now = datetime(2026, 8, 12, 13, tzinfo=UTC)
    rule = QualificationRule(
        "runtime.core",
        "1.0",
        frozenset({EvidenceKind.TEST}),
        1,
        validity_seconds=60,
    )
    result = evaluate(rule, (item,), evaluated_at=now, expected_head=item.record_hash)
    assert result.expires_at == datetime(2026, 8, 12, 13, 1, tzinfo=UTC)
