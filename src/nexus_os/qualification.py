"""Deterministic evidence-to-capability qualification rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from nexus_os.evidence import (
    EvidenceError,
    EvidenceKind,
    EvidenceOutcome,
    EvidenceRecord,
    verify_chain,
)

_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class QualificationError(ValueError):
    """Safe qualification rule or evidence failure."""


class CapabilityState(StrEnum):
    UNKNOWN = "UNKNOWN"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    QUALIFIED = "QUALIFIED"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"
    PRODUCTION = "PRODUCTION"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True, slots=True)
class QualificationRule:
    capability_id: str
    rule_version: str
    required_kinds: frozenset[EvidenceKind]
    minimum_passing_records: int
    target_state: CapabilityState = CapabilityState.QUALIFIED
    validity_seconds: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not _CAPABILITY.fullmatch(self.capability_id):
            raise QualificationError("capability_id is invalid")
        if not isinstance(self.rule_version, str) or not _VERSION.fullmatch(self.rule_version):
            raise QualificationError("rule_version is invalid")
        if not self.required_kinds:
            raise QualificationError("required_kinds must not be empty")
        if (
            not isinstance(self.minimum_passing_records, int)
            or not 1 <= self.minimum_passing_records <= 10_000
        ):
            raise QualificationError("minimum_passing_records must be from 1 to 10000")
        if self.target_state not in {
            CapabilityState.TESTED,
            CapabilityState.VERIFIED,
            CapabilityState.QUALIFIED,
        }:
            raise QualificationError("automatic qualification cannot grant production states")
        if self.validity_seconds is not None and not 1 <= self.validity_seconds <= 31_536_000:
            raise QualificationError("validity_seconds must be from 1 to 31536000")


@dataclass(frozen=True, slots=True)
class CapabilityQualification:
    capability_id: str
    state: CapabilityState
    rule_version: str
    evaluated_at: datetime
    evidence_ids: tuple[UUID, ...]
    limitations: tuple[str, ...]
    expires_at: datetime | None = None


def evaluate(
    rule: QualificationRule,
    records: tuple[EvidenceRecord, ...],
    *,
    evaluated_at: datetime,
    expected_head: str,
) -> CapabilityQualification:
    _utc(evaluated_at)
    try:
        verify_chain(records, expected_count=len(records), expected_head=expected_head)
    except EvidenceError as exc:
        raise QualificationError("evidence integrity verification failed") from exc
    passing = tuple(record for record in records if record.outcome is EvidenceOutcome.PASS)
    present_kinds = frozenset(record.kind for record in passing)
    limitations: list[str] = []
    if any(record.timestamp > evaluated_at for record in records):
        limitations.append("evidence_timestamp_is_in_the_future")
    if any(record.outcome is not EvidenceOutcome.PASS for record in records):
        limitations.append("evidence_contains_non_passing_outcome")
    missing = sorted(kind.value for kind in rule.required_kinds - present_kinds)
    if missing:
        limitations.append("missing_required_kinds:" + ",".join(missing))
    distinct_tests = {record.test_id for record in passing if record.test_id is not None}
    if len(passing) < rule.minimum_passing_records:
        limitations.append("insufficient_passing_records")
    if len(distinct_tests) != len(passing):
        limitations.append("passing_records_require_distinct_test_ids")
    qualified = not limitations
    return CapabilityQualification(
        capability_id=rule.capability_id,
        state=rule.target_state if qualified else CapabilityState.UNKNOWN,
        rule_version=rule.rule_version,
        evaluated_at=evaluated_at,
        evidence_ids=tuple(record.evidence_id for record in passing) if qualified else (),
        limitations=tuple(limitations),
        expires_at=(
            None
            if not qualified or rule.validity_seconds is None
            else evaluated_at + timedelta(seconds=rule.validity_seconds)
        ),
    )


def _utc(value: datetime) -> None:
    invalid = (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    )
    if invalid:
        raise QualificationError("evaluated_at must be timezone-aware UTC")
