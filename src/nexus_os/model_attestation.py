"""Verify independent benchmark evidence before reasoning-model qualification."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from nexus_os.domain import RunId, TraceId
from nexus_os.evidence import (
    EvidenceError,
    EvidenceKind,
    EvidenceOutcome,
    EvidenceRecord,
    verify_chain,
)
from nexus_os.model_qualification import (
    EvaluationCategory,
    EvaluationResult,
    ModelEvaluation,
    ModelQualification,
    qualify_model,
)

_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_PRODUCER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
_EXPECTED_FIELDS = {
    "schema_version",
    "run_id",
    "trace_id",
    "provider_id",
    "adapter_version",
    "model_id",
    "endpoint_digest",
    "report",
    "qualification_state",
    "manifest_digest",
}
_REPORT_FIELDS = {
    "schema_version",
    "suite_version",
    "corpus_digest",
    "evaluated_at",
    "observations",
    "category_results",
    "report_digest",
}


class ModelAttestationError(ValueError):
    """Safe manifest, evidence, or attestation verification failure."""


@dataclass(frozen=True, slots=True)
class AttestedModelQualification:
    manifest_digest: str
    evidence_count: int
    evidence_head: str
    attested_at: datetime
    attestor_producers: tuple[str, ...]
    qualification: ModelQualification
    attestation_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "manifest_digest": self.manifest_digest,
            "evidence_count": self.evidence_count,
            "evidence_head": self.evidence_head,
            "attested_at": _timestamp(self.attested_at),
            "attestor_producers": list(self.attestor_producers),
            "qualification": self.qualification.to_dict(),
            "attestation_digest": self.attestation_digest,
        }


def attest_and_qualify(
    manifest: Mapping[str, Any],
    records: tuple[EvidenceRecord, ...],
    *,
    expected_count: int,
    expected_head: str,
    trusted_producers: frozenset[str],
    qualification_id: UUID,
    attested_at: datetime,
    validity_seconds: int,
) -> AttestedModelQualification:
    """Promote only a digest-valid manifest with a trusted seven-record evidence chain."""
    parsed = _verify_manifest(manifest)
    _utc(attested_at, "attested_at")
    if expected_count != len(EvaluationCategory) or len(records) != len(EvaluationCategory):
        raise ModelAttestationError("exactly seven category evidence records are required")
    if not trusted_producers or any(
        not isinstance(item, str) or not _PRODUCER.fullmatch(item) for item in trusted_producers
    ):
        raise ModelAttestationError("trusted producer allowlist is invalid")
    try:
        verified = verify_chain(records, expected_count=expected_count, expected_head=expected_head)
    except EvidenceError as exc:
        raise ModelAttestationError("evidence chain integrity verification failed") from exc

    run_id = RunId.parse(parsed["run_id"])
    trace_id = TraceId(parsed["trace_id"])
    report = parsed["report"]
    evaluated_at = _parse_timestamp(report["evaluated_at"], "report evaluated_at")
    results = {
        EvaluationCategory(category): EvaluationResult(result)
        for category, result in report["category_results"].items()
    }
    by_category: dict[EvaluationCategory, EvidenceRecord] = {}
    for record in records:
        category = _attested_category(record.test_id, results)
        invalid = (
            record.kind is not EvidenceKind.BENCHMARK
            or record.outcome is not EvidenceOutcome.PASS
            or record.input_digest != parsed["manifest_digest"]
            or record.output_digest != report["report_digest"]
            or record.run_id != run_id
            or record.trace_id != trace_id
            or record.producer not in trusted_producers
            or record.timestamp < evaluated_at
            or record.timestamp > attested_at
            or category in by_category
        )
        if invalid:
            raise ModelAttestationError("category evidence does not match trusted evaluation")
        by_category[category] = record
    if set(by_category) != set(EvaluationCategory):
        raise ModelAttestationError("evidence does not cover every evaluation category")

    evaluations = tuple(
        ModelEvaluation(
            f"{category.value}.{report['suite_version']}",
            category,
            results[category],
            (by_category[category].evidence_id,),
            ()
            if results[category] is EvaluationResult.PASS
            else ("independently attested evaluation did not fully pass",),
        )
        for category in EvaluationCategory
    )
    qualification = qualify_model(
        qualification_id=qualification_id,
        provider_id=parsed["provider_id"],
        model_id=parsed["model_id"],
        adapter_version=parsed["adapter_version"],
        evaluated_at=attested_at,
        validity_seconds=validity_seconds,
        evaluations=evaluations,
    )
    producers = tuple(sorted({record.producer for record in records}))
    unsigned = {
        "schema_version": "1.0",
        "manifest_digest": parsed["manifest_digest"],
        "evidence_count": verified.record_count,
        "evidence_head": verified.head_hash,
        "attested_at": _timestamp(attested_at),
        "attestor_producers": list(producers),
        "qualification": qualification.to_dict(),
    }
    return AttestedModelQualification(
        parsed["manifest_digest"],
        verified.record_count,
        verified.head_hash,
        attested_at,
        producers,
        qualification,
        _sha256(_canonical(unsigned)),
    )


def _verify_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping) or set(manifest) != _EXPECTED_FIELDS:
        raise ModelAttestationError("evaluation manifest fields are invalid")
    loaded = json.loads(_canonical(manifest))
    if not isinstance(loaded, dict):
        raise ModelAttestationError("evaluation manifest must be an object")
    parsed: dict[str, Any] = loaded
    if parsed["schema_version"] != "1.0" or parsed["qualification_state"] != "NOT_QUALIFIED":
        raise ModelAttestationError("evaluation manifest state is invalid")
    if not isinstance(parsed["report"], dict) or set(parsed["report"]) != _REPORT_FIELDS:
        raise ModelAttestationError("evaluation report fields are invalid")
    if not _DIGEST.fullmatch(str(parsed["manifest_digest"])):
        raise ModelAttestationError("evaluation manifest digest is invalid")
    unsigned = {key: value for key, value in parsed.items() if key != "manifest_digest"}
    if _sha256(_canonical(unsigned)) != parsed["manifest_digest"]:
        raise ModelAttestationError("evaluation manifest digest mismatch")
    report = parsed["report"]
    if not _DIGEST.fullmatch(str(report["report_digest"])):
        raise ModelAttestationError("evaluation report digest is invalid")
    unsigned_report = {key: value for key, value in report.items() if key != "report_digest"}
    if _sha256(_canonical(unsigned_report)) != report["report_digest"]:
        raise ModelAttestationError("evaluation report digest mismatch")
    categories = report["category_results"]
    if not isinstance(categories, dict) or set(categories) != {
        item.value for item in EvaluationCategory
    }:
        raise ModelAttestationError("evaluation report categories are invalid")
    try:
        for value in categories.values():
            EvaluationResult(value)
        RunId.parse(parsed["run_id"])
        TraceId(parsed["trace_id"])
        _parse_timestamp(report["evaluated_at"], "report evaluated_at")
    except (TypeError, ValueError) as exc:
        raise ModelAttestationError("evaluation manifest identity or result is invalid") from exc
    return parsed


def _attested_category(
    test_id: str | None, results: Mapping[EvaluationCategory, EvaluationResult]
) -> EvaluationCategory:
    for category, result in results.items():
        if test_id == f"model-evaluation:{category.value}:{result.value}":
            return category
    raise ModelAttestationError("evidence test identifier does not bind a category result")


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ModelAttestationError(f"{field} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ModelAttestationError(f"{field} is invalid") from exc
    _utc(parsed, field)
    return parsed


def _utc(value: datetime, field: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise ModelAttestationError(f"{field} must be timezone-aware UTC")


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ModelAttestationError("attestation input is not canonical JSON") from exc


def _sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"
