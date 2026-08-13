"""Deterministic evidence-derived qualification for untrusted reasoning models."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from nexus_os.secrets import redact

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_PROVIDER = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MODEL = re.compile(r"^[^\x00-\x1f\x7f]{1,200}$")
_MAX_VALIDITY_SECONDS = 7_776_000


class ModelQualificationError(ValueError):
    """Safe validation failure at the model-qualification boundary."""


class EvaluationCategory(StrEnum):
    SCHEMA_CONFORMANCE = "schema_conformance"
    PLANNING = "planning"
    TOOL_SELECTION = "tool_selection"
    APPROVAL_BOUNDARY = "approval_boundary"
    EVIDENCE_GROUNDING = "evidence_grounding"
    ADVERSARIAL_INPUT = "adversarial_input"
    BOUNDED_REPAIR = "bounded_repair"


class EvaluationResult(StrEnum):
    PASS = "PASS"  # noqa: S105 - evaluation result, not a credential
    FAIL = "FAIL"
    LIMITED = "LIMITED"


class ModelUse(StrEnum):
    CLARIFICATION = "clarification"
    CANDIDATE_SPECIFICATION = "candidate_specification"
    TASK_PLANNING = "task_planning"
    TOOL_SELECTION = "tool_selection"
    REPAIR_PROPOSAL = "repair_proposal"
    RESULT_EXPLANATION = "result_explanation"
    SENSITIVE_ACTION_PROPOSAL = "sensitive_action_proposal"


class ModelQualificationState(StrEnum):
    UNQUALIFIED = "UNQUALIFIED"
    LIMITED = "LIMITED"
    QUALIFIED = "QUALIFIED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class ModelEvaluation:
    evaluation_id: str
    category: EvaluationCategory
    result: EvaluationResult
    evidence_ids: tuple[UUID, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation_id, str) or not _IDENTIFIER.fullmatch(self.evaluation_id):
            raise ModelQualificationError("evaluation_id is invalid")
        if not isinstance(self.category, EvaluationCategory):
            raise ModelQualificationError("evaluation category is invalid")
        if not isinstance(self.result, EvaluationResult):
            raise ModelQualificationError("evaluation result is invalid")
        if not self.evidence_ids or len(self.evidence_ids) > 64:
            raise ModelQualificationError("evaluation requires from 1 to 64 evidence identifiers")
        if any(not isinstance(item, UUID) for item in self.evidence_ids):
            raise ModelQualificationError("evidence_ids must contain UUID values")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ModelQualificationError("evidence_ids must be unique")
        if len(self.limitations) > 32:
            raise ModelQualificationError("evaluation has too many limitations")
        for limitation in self.limitations:
            _bounded_text(limitation, "evaluation limitation", 1000)
            if redact(limitation) != limitation:
                raise ModelQualificationError("evaluation limitation contains secret-like material")
        if self.result is not EvaluationResult.PASS and not self.limitations:
            raise ModelQualificationError("non-passing evaluation requires a limitation")

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "evaluation_id": self.evaluation_id,
            "category": self.category.value,
            "result": self.result.value,
            "evidence_ids": [str(item) for item in self.evidence_ids],
        }
        if self.limitations:
            value["limitations"] = list(self.limitations)
        return value


@dataclass(frozen=True, slots=True)
class ModelQualification:
    qualification_id: UUID
    provider_id: str
    model_id: str
    adapter_version: str
    evaluated_at: datetime
    expires_at: datetime
    evaluations: tuple[ModelEvaluation, ...]
    allowed_uses: tuple[ModelUse, ...]
    state: ModelQualificationState
    limitations: tuple[str, ...]
    evidence_digest: str

    def effective_state(self, *, at: datetime) -> ModelQualificationState:
        _utc(at, "at")
        return ModelQualificationState.EXPIRED if at >= self.expires_at else self.state

    def permits(self, use: ModelUse, *, at: datetime) -> bool:
        return (
            self.effective_state(at=at) is not ModelQualificationState.EXPIRED
            and use in self.allowed_uses
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "qualification_id": str(self.qualification_id),
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "adapter_version": self.adapter_version,
            "evaluated_at": _timestamp(self.evaluated_at),
            "expires_at": _timestamp(self.expires_at),
            "evaluations": [item.to_dict() for item in self.evaluations],
            "allowed_uses": [item.value for item in self.allowed_uses],
            "state": self.state.value,
            "limitations": list(self.limitations),
            "evidence_digest": self.evidence_digest,
        }


_REQUIREMENTS: dict[ModelUse, frozenset[EvaluationCategory]] = {
    ModelUse.CLARIFICATION: frozenset({EvaluationCategory.SCHEMA_CONFORMANCE}),
    ModelUse.RESULT_EXPLANATION: frozenset(
        {EvaluationCategory.SCHEMA_CONFORMANCE, EvaluationCategory.EVIDENCE_GROUNDING}
    ),
    ModelUse.CANDIDATE_SPECIFICATION: frozenset(
        {
            EvaluationCategory.SCHEMA_CONFORMANCE,
            EvaluationCategory.PLANNING,
            EvaluationCategory.EVIDENCE_GROUNDING,
            EvaluationCategory.ADVERSARIAL_INPUT,
        }
    ),
    ModelUse.TASK_PLANNING: frozenset(
        {
            EvaluationCategory.SCHEMA_CONFORMANCE,
            EvaluationCategory.PLANNING,
            EvaluationCategory.APPROVAL_BOUNDARY,
            EvaluationCategory.EVIDENCE_GROUNDING,
            EvaluationCategory.ADVERSARIAL_INPUT,
        }
    ),
    ModelUse.TOOL_SELECTION: frozenset(
        {
            EvaluationCategory.SCHEMA_CONFORMANCE,
            EvaluationCategory.TOOL_SELECTION,
            EvaluationCategory.APPROVAL_BOUNDARY,
            EvaluationCategory.ADVERSARIAL_INPUT,
        }
    ),
    ModelUse.REPAIR_PROPOSAL: frozenset(
        {
            EvaluationCategory.SCHEMA_CONFORMANCE,
            EvaluationCategory.APPROVAL_BOUNDARY,
            EvaluationCategory.ADVERSARIAL_INPUT,
            EvaluationCategory.BOUNDED_REPAIR,
        }
    ),
    ModelUse.SENSITIVE_ACTION_PROPOSAL: frozenset(EvaluationCategory),
}


def qualify_model(
    *,
    qualification_id: UUID,
    provider_id: str,
    model_id: str,
    adapter_version: str,
    evaluated_at: datetime,
    validity_seconds: int,
    evaluations: tuple[ModelEvaluation, ...],
) -> ModelQualification:
    """Derive model uses from one externally evidenced result per required category."""
    if not isinstance(qualification_id, UUID):
        raise ModelQualificationError("qualification_id must be a UUID")
    if not isinstance(provider_id, str) or not _PROVIDER.fullmatch(provider_id):
        raise ModelQualificationError("provider_id is invalid")
    if not isinstance(model_id, str) or not _MODEL.fullmatch(model_id):
        raise ModelQualificationError("model_id is invalid")
    if not isinstance(adapter_version, str) or not _VERSION.fullmatch(adapter_version):
        raise ModelQualificationError("adapter_version is invalid")
    _utc(evaluated_at, "evaluated_at")
    if (
        not isinstance(validity_seconds, int)
        or isinstance(validity_seconds, bool)
        or not 1 <= validity_seconds <= _MAX_VALIDITY_SECONDS
    ):
        raise ModelQualificationError("validity_seconds must be from 1 to 7776000")
    if any(not isinstance(item, ModelEvaluation) for item in evaluations):
        raise ModelQualificationError("evaluations must contain ModelEvaluation values")
    by_category = {item.category: item for item in evaluations}
    if len(evaluations) != len(EvaluationCategory) or set(by_category) != set(EvaluationCategory):
        raise ModelQualificationError("exactly one evaluation per required category is required")
    evidence_ids = [identifier for item in evaluations for identifier in item.evidence_ids]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ModelQualificationError("evidence identifiers must be unique across evaluations")

    passing = {
        category for category, item in by_category.items() if item.result is EvaluationResult.PASS
    }
    allowed = tuple(use for use in ModelUse if _REQUIREMENTS[use] <= passing)
    state = (
        ModelQualificationState.QUALIFIED
        if len(passing) == len(EvaluationCategory)
        else ModelQualificationState.LIMITED
        if allowed
        else ModelQualificationState.UNQUALIFIED
    )
    limitations = tuple(
        f"{item.category.value}:{limitation}"
        for item in evaluations
        if item.result is not EvaluationResult.PASS
        for limitation in item.limitations
    )
    ordered = tuple(sorted(evaluations, key=lambda item: item.category.value))
    unsigned = {
        "schema_version": "1.0",
        "qualification_id": str(qualification_id),
        "provider_id": provider_id,
        "model_id": model_id,
        "adapter_version": adapter_version,
        "evaluated_at": _timestamp(evaluated_at),
        "expires_at": _timestamp(evaluated_at + timedelta(seconds=validity_seconds)),
        "evaluations": [item.to_dict() for item in ordered],
        "allowed_uses": [item.value for item in allowed],
        "state": state.value,
        "limitations": list(limitations),
    }
    digest = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    return ModelQualification(
        qualification_id,
        provider_id,
        model_id,
        adapter_version,
        evaluated_at,
        evaluated_at + timedelta(seconds=validity_seconds),
        ordered,
        allowed,
        state,
        limitations,
        digest,
    )


def _bounded_text(value: object, field: str, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or any(ord(character) < 32 and character not in "\t\n\r" for character in value)
    ):
        raise ModelQualificationError(f"{field} is invalid")


def _utc(value: datetime, field: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise ModelQualificationError(f"{field} must be timezone-aware UTC")


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
