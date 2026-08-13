"""Controlled, deterministic evaluation of reasoning-provider structured outputs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

from nexus_os.domain import RunId, TaskId, TaskStatus, TraceId
from nexus_os.model_qualification import (
    EvaluationCategory,
    EvaluationResult,
    ModelEvaluation,
)
from nexus_os.providers import AgentAdapter, ProviderTask
from nexus_os.secrets import redact

_CASE_ID = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_SUITE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MAX_CASES = 256
_MAX_PROMPT = 20_000
_MAX_OUTPUT = 100_000


class ModelEvaluationError(ValueError):
    """Safe evaluation-boundary or corpus validation failure."""


class CaseStatus(StrEnum):
    PASS = "PASS"  # noqa: S105 - evaluation status, not a credential
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class ModelEvaluationCase:
    case_id: str
    category: EvaluationCategory
    prompt: str
    expected_output: Mapping[str, Any]
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not _CASE_ID.fullmatch(self.case_id):
            raise ModelEvaluationError("case_id is invalid")
        if not isinstance(self.category, EvaluationCategory):
            raise ModelEvaluationError("case category is invalid")
        _bounded_text(self.prompt, "prompt", _MAX_PROMPT)
        if redact(self.prompt) != self.prompt:
            raise ModelEvaluationError("prompt contains secret-like material")
        if (
            not isinstance(self.timeout_seconds, int)
            or isinstance(self.timeout_seconds, bool)
            or not 1 <= self.timeout_seconds <= 300
        ):
            raise ModelEvaluationError("timeout_seconds must be from 1 to 300")
        expected = _canonical_object(self.expected_output, "expected_output")
        object.__setattr__(self, "expected_output", MappingProxyType(expected))

    def canonical(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category.value,
            "prompt": self.prompt,
            "expected_output": dict(self.expected_output),
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True, slots=True)
class ModelEvaluationSuite:
    suite_version: str
    cases: tuple[ModelEvaluationCase, ...]
    corpus_digest: str

    @classmethod
    def create(
        cls, suite_version: str, cases: tuple[ModelEvaluationCase, ...]
    ) -> ModelEvaluationSuite:
        if not isinstance(suite_version, str) or not _SUITE_VERSION.fullmatch(suite_version):
            raise ModelEvaluationError("suite_version is invalid")
        if not 7 <= len(cases) <= _MAX_CASES:
            raise ModelEvaluationError("evaluation suite requires from 7 to 256 cases")
        if any(not isinstance(case, ModelEvaluationCase) for case in cases):
            raise ModelEvaluationError("suite cases are invalid")
        identifiers = [case.case_id for case in cases]
        if len(identifiers) != len(set(identifiers)):
            raise ModelEvaluationError("case identifiers must be unique")
        if {case.category for case in cases} != set(EvaluationCategory):
            raise ModelEvaluationError("suite must cover every required category")
        ordered = tuple(sorted(cases, key=lambda case: case.case_id))
        payload = {
            "schema_version": "1.0",
            "suite_version": suite_version,
            "cases": [case.canonical() for case in ordered],
        }
        digest = _digest(payload)
        return cls(suite_version, ordered, digest)


@dataclass(frozen=True, slots=True)
class CaseObservation:
    case_id: str
    category: EvaluationCategory
    status: CaseStatus
    output_digest: str
    failure_code: str | None

    def canonical(self) -> dict[str, str | None]:
        return {
            "case_id": self.case_id,
            "category": self.category.value,
            "status": self.status.value,
            "output_digest": self.output_digest,
            "failure_code": self.failure_code,
        }


@dataclass(frozen=True, slots=True)
class ModelEvaluationReport:
    suite_version: str
    corpus_digest: str
    evaluated_at: datetime
    observations: tuple[CaseObservation, ...]
    category_results: Mapping[EvaluationCategory, EvaluationResult]
    report_digest: str

    def bind_evidence(
        self, evidence_ids: Mapping[EvaluationCategory, UUID]
    ) -> tuple[ModelEvaluation, ...]:
        if set(evidence_ids) != set(EvaluationCategory) or any(
            not isinstance(item, UUID) for item in evidence_ids.values()
        ):
            raise ModelEvaluationError("one evidence UUID per category is required")
        if len(set(evidence_ids.values())) != len(EvaluationCategory):
            raise ModelEvaluationError("category evidence UUIDs must be unique")
        return tuple(
            ModelEvaluation(
                f"{category.value}.{self.suite_version}",
                category,
                self.category_results[category],
                (evidence_ids[category],),
                ()
                if self.category_results[category] is EvaluationResult.PASS
                else ("one or more controlled evaluation cases did not pass",),
            )
            for category in EvaluationCategory
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "suite_version": self.suite_version,
            "corpus_digest": self.corpus_digest,
            "evaluated_at": self.evaluated_at.isoformat().replace("+00:00", "Z"),
            "observations": [item.canonical() for item in self.observations],
            "category_results": {
                category.value: self.category_results[category].value
                for category in EvaluationCategory
            },
            "report_digest": self.report_digest,
        }


class ModelEvaluationRunner:
    """Run a fixed corpus through an adapter without granting provider authority."""

    def __init__(self, suite: ModelEvaluationSuite) -> None:
        if not isinstance(suite, ModelEvaluationSuite):
            raise ModelEvaluationError("suite is invalid")
        self._suite = suite

    async def run(
        self,
        adapter: AgentAdapter,
        *,
        run_id: RunId,
        trace_id: TraceId,
        evaluated_at: datetime,
    ) -> ModelEvaluationReport:
        _utc(evaluated_at)
        observations = tuple(
            [await self._run_case(adapter, case, run_id, trace_id) for case in self._suite.cases]
        )
        results = {
            category: _category_result(observations, category) for category in EvaluationCategory
        }
        unsigned = {
            "schema_version": "1.0",
            "suite_version": self._suite.suite_version,
            "corpus_digest": self._suite.corpus_digest,
            "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z"),
            "observations": [item.canonical() for item in observations],
            "category_results": {
                category.value: results[category].value for category in EvaluationCategory
            },
        }
        return ModelEvaluationReport(
            self._suite.suite_version,
            self._suite.corpus_digest,
            evaluated_at,
            observations,
            MappingProxyType(results),
            _digest(unsigned),
        )

    async def _run_case(
        self,
        adapter: AgentAdapter,
        case: ModelEvaluationCase,
        run_id: RunId,
        trace_id: TraceId,
    ) -> CaseObservation:
        task_id = hashlib.sha256(case.case_id.encode()).hexdigest()[:24]
        provider_task_id = f"model-eval-{task_id}"
        task = ProviderTask(
            provider_task_id,
            run_id,
            TaskId(f"model_eval_{task_id}"),
            trace_id,
            "reasoning_evaluation",
            {
                "system": "Return only the requested JSON object. Do not execute tools.",
                "prompt": case.prompt,
            },
            case.timeout_seconds,
        )
        try:
            identity = await asyncio.wait_for(adapter.run(task), timeout=case.timeout_seconds)
            if identity != provider_task_id:
                return _failed(case, "provider_identity_mismatch")
            result = await asyncio.wait_for(adapter.result(identity), timeout=case.timeout_seconds)
            if result.status is not TaskStatus.SUCCEEDED:
                return _failed(case, "provider_result_failed")
            output = result.metadata.get("output_text")
            if not isinstance(output, str) or not 1 <= len(output) <= _MAX_OUTPUT:
                return _failed(case, "output_missing_or_oversized")
            output_digest = _text_digest(output)
            parsed = _strict_json_object(output)
            if parsed != dict(case.expected_output):
                return CaseObservation(
                    case.case_id,
                    case.category,
                    CaseStatus.FAIL,
                    output_digest,
                    "rubric_mismatch",
                )
            return CaseObservation(
                case.case_id, case.category, CaseStatus.PASS, output_digest, None
            )
        except TimeoutError:
            try:
                await adapter.cancel(provider_task_id)
            except Exception:
                return _failed(case, "provider_timeout")
            return _failed(case, "provider_timeout")
        except Exception:
            return _failed(case, "provider_boundary_error")


def _category_result(
    observations: tuple[CaseObservation, ...], category: EvaluationCategory
) -> EvaluationResult:
    statuses = [item.status for item in observations if item.category is category]
    passed = sum(status is CaseStatus.PASS for status in statuses)
    if passed == len(statuses):
        return EvaluationResult.PASS
    return EvaluationResult.LIMITED if passed else EvaluationResult.FAIL


def _failed(case: ModelEvaluationCase, code: str) -> CaseObservation:
    return CaseObservation(case.case_id, case.category, CaseStatus.FAIL, _text_digest(""), code)


def _strict_json_object(value: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise ModelEvaluationError("model output contains duplicate JSON keys")
            result[key] = item
        return result

    parsed = json.loads(value, object_pairs_hook=pairs)
    return _canonical_object(parsed, "model output")


def _canonical_object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelEvaluationError(f"{field} must be an object")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        parsed = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ModelEvaluationError(f"{field} must contain canonical JSON values") from exc
    if not isinstance(parsed, dict) or len(encoded) > _MAX_OUTPUT:
        raise ModelEvaluationError(f"{field} is invalid or oversized")
    if redact(parsed) != parsed:
        raise ModelEvaluationError(f"{field} contains secret-like material")
    return parsed


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _text_digest(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"


def _bounded_text(value: object, field: str, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or any(ord(character) < 32 and character not in "\t\n\r" for character in value)
    ):
        raise ModelEvaluationError(f"{field} is invalid")


def _utc(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise ModelEvaluationError("evaluated_at must be timezone-aware UTC")
