"""Governed capital-allocation review workflow for RAD Operations."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any, TypeGuard, cast
from uuid import UUID, uuid4

from nexus_os.approval import ApprovalStore
from nexus_os.capabilities import RouteRequest
from nexus_os.domain import ActionEffect, RunId, TaskId, TraceId
from nexus_os.evidence import (
    GENESIS,
    EvidenceKind,
    EvidenceLedger,
    EvidenceOutcome,
    EvidenceRecord,
)
from nexus_os.node import NodePrincipal, RadNode

_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{1,127}$")
_MAX_INPUT_BYTES = 1_000_000
_MAX_VALIDITY = timedelta(days=31)
_CAPABILITY_ID = "rad.decision.financial"
_CAPABILITY_VERSION = "0.2.0"
_OPERATION = "portfolio.allocate"


class CapitalPlanningError(ValueError):
    """Safe workflow contract, approval, execution, or verification failure."""


@dataclass(frozen=True, slots=True)
class CapitalSnapshot:
    source_id: str
    observed_at: datetime
    valid_until: datetime
    source_digest: str
    asset_ids: tuple[str, ...]
    request: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CapitalPlan:
    project_id: str
    run_id: RunId
    trace_id: TraceId
    snapshot: CapitalSnapshot
    plan_digest: str
    approval_effect: ActionEffect = ActionEffect.SENSITIVE

    def canonical(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "workflow": "rad.operations.capital_planning",
            "project_id": self.project_id,
            "run_id": str(self.run_id),
            "trace_id": str(self.trace_id),
            "source": {
                "source_id": self.snapshot.source_id,
                "observed_at": _timestamp(self.snapshot.observed_at),
                "valid_until": _timestamp(self.snapshot.valid_until),
                "source_digest": self.snapshot.source_digest,
            },
            "asset_ids": list(self.snapshot.asset_ids),
            "engine_request": dict(self.snapshot.request),
            "engine_binding": {
                "capability_id": _CAPABILITY_ID,
                "version": _CAPABILITY_VERSION,
                "operation": _OPERATION,
                "network": "DENIED",
            },
            "approval_effect": self.approval_effect.value,
            "acceptance": [
                "engine_identity_and_request_digest_verified",
                "allocation_is_feasible",
                "utility_is_not_worse_than_baseline",
                "execution_authority_is_denied",
                "evidence_chain_is_verified",
            ],
        }


@dataclass(frozen=True, slots=True)
class CapitalDossier:
    document: Mapping[str, Any]
    dossier_digest: str
    evidence_head: str
    evidence_count: int

    def canonical(self) -> dict[str, Any]:
        return {
            **dict(self.document),
            "dossier_digest": self.dossier_digest,
            "evidence": {"record_count": self.evidence_count, "head_hash": self.evidence_head},
        }


def ingest_capital_snapshot(payload: bytes, *, now: datetime) -> CapitalSnapshot:
    """Ingest a bounded, current JSON snapshot without granting source-system access."""
    _utc(now, "now")
    if not isinstance(payload, bytes) or not 1 <= len(payload) <= _MAX_INPUT_BYTES:
        raise CapitalPlanningError("capital snapshot is empty or oversized")
    try:
        raw = payload.decode("utf-8")
        document = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, CapitalPlanningError) as exc:
        raise CapitalPlanningError("capital snapshot is not strict UTF-8 JSON") from exc
    fields = {
        "schema_version",
        "source_id",
        "observed_at",
        "valid_until",
        "asset_ids",
        "expected_returns",
        "covariance",
        "previous_weights",
        "policy",
    }
    if not isinstance(document, dict) or set(document) != fields:
        raise CapitalPlanningError("capital snapshot fields are invalid")
    if document["schema_version"] != "1.0" or not isinstance(document["source_id"], str):
        raise CapitalPlanningError("capital snapshot identity is invalid")
    if not _SOURCE_ID.fullmatch(document["source_id"]):
        raise CapitalPlanningError("capital snapshot source_id is invalid")
    observed = _parse_timestamp(document["observed_at"], "observed_at")
    valid_until = _parse_timestamp(document["valid_until"], "valid_until")
    if observed > now or not observed < valid_until or now >= valid_until:
        raise CapitalPlanningError("capital snapshot is not currently valid")
    if valid_until - observed > _MAX_VALIDITY:
        raise CapitalPlanningError("capital snapshot validity exceeds 31 days")
    assets = document["asset_ids"]
    if (
        not isinstance(assets, list)
        or not 2 <= len(assets) <= 64
        or any(not isinstance(item, str) or not _SOURCE_ID.fullmatch(item) for item in assets)
        or len(set(assets)) != len(assets)
    ):
        raise CapitalPlanningError("capital snapshot asset_ids are invalid")
    policy = document["policy"]
    policy_fields = {
        "risk_aversion",
        "transaction_cost",
        "cardinality_penalty",
        "min_position",
        "max_assets",
        "steps",
        "seed",
    }
    if not isinstance(policy, dict) or set(policy) != policy_fields:
        raise CapitalPlanningError("capital snapshot policy is invalid")
    request = {
        "expected_returns": document["expected_returns"],
        "covariance": document["covariance"],
        "previous_weights": document["previous_weights"],
        **policy,
    }
    _validate_request_shape(request, len(assets))
    canonical = _canonical(document)
    return CapitalSnapshot(
        document["source_id"],
        observed,
        valid_until,
        _digest_bytes(canonical),
        tuple(assets),
        MappingProxyType(json.loads(_canonical(request))),
    )


def prepare_capital_plan(
    snapshot: CapitalSnapshot, *, project_id: str, run_id: RunId, trace_id: TraceId
) -> CapitalPlan:
    """Produce a reviewable plan bound to source, engine, policy, and acceptance."""
    if not isinstance(snapshot, CapitalSnapshot):
        raise CapitalPlanningError("capital snapshot is invalid")
    if not isinstance(project_id, str) or not project_id.strip() or len(project_id) > 256:
        raise CapitalPlanningError("project_id is invalid")
    if not isinstance(run_id, RunId) or not isinstance(trace_id, TraceId):
        raise CapitalPlanningError("run or trace identity is invalid")
    draft = CapitalPlan(project_id, run_id, trace_id, snapshot, "")
    return CapitalPlan(project_id, run_id, trace_id, snapshot, _digest(draft.canonical()))


class CapitalPlanningWorkflow:
    """Execute one exact approved recommendation and produce downloadable evidence."""

    def __init__(self, node: RadNode, approvals: ApprovalStore, evidence: EvidenceLedger) -> None:
        if not isinstance(node, RadNode):
            raise CapitalPlanningError("RAD Node is required")
        self._node = node
        self._approvals = approvals
        self._evidence = evidence

    async def execute(
        self,
        plan: CapitalPlan,
        approval_id: UUID,
        principal: NodePrincipal,
        *,
        now: datetime,
    ) -> CapitalDossier:
        _utc(now, "now")
        if now >= plan.snapshot.valid_until:
            raise CapitalPlanningError("approved plan source data has expired")
        if self._evidence.records(plan.project_id, plan.run_id):
            raise CapitalPlanningError("capital planning run already contains evidence")
        if _digest({key: value for key, value in plan.canonical().items()}) != plan.plan_digest:
            raise CapitalPlanningError("capital plan digest is invalid")
        try:
            approval = self._approvals.authorize_and_consume(
                approval_id,
                project_id=plan.project_id,
                run_id=plan.run_id,
                action_digest=plan.plan_digest,
                now=now,
            )
        except Exception as exc:
            raise CapitalPlanningError("exact capital plan approval is required") from exc
        request = dict(plan.snapshot.request)
        route = RouteRequest(
            _CAPABILITY_ID,
            _OPERATION,
            frozenset({ActionEffect.READ_ONLY}),
            version=_CAPABILITY_VERSION,
            max_timeout_seconds=300,
            max_memory_mib=4096,
        )
        try:
            execution = await self._node.execute(route, request, principal, at=now)
        except Exception as exc:
            raise CapitalPlanningError("qualified capital decision execution failed") from exc
        result = dict(execution.output)
        checks = _verify_result(plan, result)
        if not all(checks.values()):
            raise CapitalPlanningError("capital recommendation failed acceptance verification")
        decision = dict(result["decision"])
        weights = decision["weights"]
        baseline_utility = _utility(
            plan.snapshot.request["previous_weights"], plan.snapshot.request
        )
        recommendation = [
            {"asset_id": asset, "weight": weights[index]}
            for index, asset in enumerate(plan.snapshot.asset_ids)
        ]
        document = {
            "schema_version": "1.0",
            "workflow": "rad.operations.capital_planning",
            "status": "VERIFIED_RECOMMENDATION_REQUIRES_EXTERNAL_ACTION_APPROVAL",
            "project_id": plan.project_id,
            "run_id": str(plan.run_id),
            "trace_id": str(plan.trace_id),
            "plan_digest": plan.plan_digest,
            "source": plan.canonical()["source"],
            "engine": {
                "engine_id": result["engine_id"],
                "engine_version": result["engine_version"],
                "adapter_version": result["adapter_version"],
                "capability_id": result["capability_id"],
                "request_digest": result["request_digest"],
                "lease_id": str(execution.lease_id),
            },
            "observations": {"asset_count": len(plan.snapshot.asset_ids)},
            "assumptions": [
                "expected_returns_and_covariance_are_operator_supplied",
                "risk_and_return_estimates_may_not_predict_future_conditions",
            ],
            "recommendation": recommendation,
            "expected_outcome": {
                "expected_return": decision["expected_return"],
                "volatility": decision["volatility"],
                "utility": decision["utility"],
                "baseline_utility": baseline_utility,
                "utility_improvement": decision["utility"] - baseline_utility,
            },
            "downside_risk": {
                "value_at_risk_95_normal_assumption": decision[
                    "value_at_risk_95_normal_assumption"
                ],
                "conditional_value_at_risk_95_normal_assumption": decision[
                    "conditional_value_at_risk_95_normal_assumption"
                ],
            },
            "acceptance": checks,
            "execution_authorized": False,
            "required_approval": "separate_external_action_approval",
            "valid_until": _timestamp(plan.snapshot.valid_until),
            "limitations": sorted(set(result["limitations"] + ["operator_supplied_snapshot"])),
        }
        dossier_digest = _digest(document)
        records = self._append_evidence(plan, approval.decided_by or "unknown", dossier_digest, now)
        verification = self._evidence.verify(plan.project_id, plan.run_id)
        if verification.record_count != len(records):
            raise CapitalPlanningError("capital evidence scope contains unexpected records")
        return CapitalDossier(
            MappingProxyType(document), dossier_digest, verification.head_hash, len(records)
        )

    def export_evidence(self, dossier: CapitalDossier) -> bytes:
        """Return a canonical, integrity-rechecked dossier and evidence bundle."""
        document = dossier.canonical()
        run_id = RunId.parse(document["run_id"])
        verification = self._evidence.verify(str(document["project_id"]), run_id)
        if (
            verification.head_hash != dossier.evidence_head
            or verification.record_count != dossier.evidence_count
            or _digest(dict(dossier.document)) != dossier.dossier_digest
        ):
            raise CapitalPlanningError("capital evidence export failed integrity verification")
        document["evidence"]["records"] = [
            item.to_dict() for item in self._evidence.records(str(document["project_id"]), run_id)
        ]
        return _canonical(document)

    def _append_evidence(
        self, plan: CapitalPlan, approver: str, dossier_digest: str, now: datetime
    ) -> tuple[EvidenceRecord, ...]:
        specifications = (
            (
                EvidenceKind.SPECIFICATION,
                "capital_plan",
                plan.snapshot.source_digest,
                plan.plan_digest,
            ),
            (EvidenceKind.APPROVAL, "capital_plan_approval", plan.plan_digest, plan.plan_digest),
            (EvidenceKind.TEST, "capital_acceptance", plan.plan_digest, dossier_digest),
            (EvidenceKind.ARTIFACT, "capital_dossier", plan.plan_digest, dossier_digest),
        )
        records: list[EvidenceRecord] = []
        head = GENESIS
        for sequence, (kind, test_id, input_digest, output_digest) in enumerate(
            specifications, start=1
        ):
            actor = approver if kind is EvidenceKind.APPROVAL else "rad-operations"
            record = EvidenceRecord(
                uuid4(),
                sequence,
                now,
                plan.project_id,
                plan.run_id,
                TaskId("capital_review"),
                actor,
                "rad.operations.capital_planning@1.0.0",
                kind,
                EvidenceOutcome.PASS,
                test_id,
                input_digest,
                output_digest,
                plan.trace_id,
                head,
            )
            sealed = self._evidence.append(record, expected_head=head)
            records.append(sealed)
            head = sealed.record_hash
        return tuple(records)


def _verify_result(plan: CapitalPlan, result: Mapping[str, Any]) -> dict[str, bool]:
    decision = result.get("decision")
    weights = decision.get("weights") if isinstance(decision, Mapping) else None
    feasible = (
        isinstance(weights, list)
        and len(weights) == len(plan.snapshot.asset_ids)
        and all(_number(item) and 0 <= item <= 1 for item in weights)
        and math.isclose(sum(weights), 1.0, abs_tol=1e-8)
        and sum(item > 1e-6 for item in weights) <= plan.snapshot.request["max_assets"]
    )
    expected_request = {"operation": _OPERATION, **dict(plan.snapshot.request)}
    identity = (
        result.get("engine_id") == "financial-algorithm"
        and result.get("engine_version") == _CAPABILITY_VERSION
        and result.get("adapter_version") == "1.0.0"
        and result.get("capability_id") == _CAPABILITY_ID
        and result.get("request_digest") == _digest(expected_request)
    )
    utility = decision.get("utility") if isinstance(decision, Mapping) else None
    baseline = _utility(plan.snapshot.request["previous_weights"], plan.snapshot.request)
    return {
        "engine_identity_and_request_digest_verified": identity,
        "allocation_is_feasible": feasible,
        "utility_is_not_worse_than_baseline": _number(utility) and utility + 1e-12 >= baseline,
        "execution_authority_is_denied": result.get("execution_authorized") is False,
        "evidence_chain_is_verified": True,
    }


def _validate_request_shape(request: Mapping[str, Any], size: int) -> None:
    vectors = (request.get("expected_returns"), request.get("previous_weights"))
    if any(
        not isinstance(value, list)
        or len(value) != size
        or any(not _number(item) for item in value)
        for value in vectors
    ):
        raise CapitalPlanningError("capital snapshot vectors are invalid")
    covariance = request.get("covariance")
    if (
        not isinstance(covariance, list)
        or len(covariance) != size
        or any(
            not isinstance(row, list) or len(row) != size or any(not _number(item) for item in row)
            for row in covariance
        )
    ):
        raise CapitalPlanningError("capital snapshot covariance is invalid")
    if not math.isclose(sum(request["previous_weights"]), 1.0, abs_tol=1e-8):
        raise CapitalPlanningError("previous weights must sum to one")
    if any(not -5 <= value <= 5 for value in request["expected_returns"]) or any(
        not 0 <= value <= 1 for value in request["previous_weights"]
    ):
        raise CapitalPlanningError("capital snapshot vectors are outside bounded limits")
    if any(
        not math.isclose(covariance[row][column], covariance[column][row], abs_tol=1e-10)
        for row in range(size)
        for column in range(size)
    ) or not _positive_semidefinite(covariance):
        raise CapitalPlanningError("capital snapshot covariance is not positive semidefinite")
    numeric_bounds = {
        "risk_aversion": (0.01, 100),
        "transaction_cost": (0, 1),
        "cardinality_penalty": (0, 1),
        "min_position": (0, 1),
    }
    if any(not _bounded(request.get(key), *bounds) for key, bounds in numeric_bounds.items()):
        raise CapitalPlanningError("capital snapshot policy is outside bounded limits")
    if (
        not _integer(request.get("max_assets"), 1, size)
        or not _integer(request.get("steps"), 100, 100_000)
        or not _integer(request.get("seed"), 0, 2**32 - 1)
    ):
        raise CapitalPlanningError("capital snapshot policy is outside bounded limits")


def _utility(weights: Sequence[float], request: Mapping[str, Any]) -> float:
    returns = cast(Sequence[float], request["expected_returns"])
    covariance = cast(Sequence[Sequence[float]], request["covariance"])
    expected = sum(weight * returns[index] for index, weight in enumerate(weights))
    variance = sum(
        weights[row] * covariance[row][column] * weights[column]
        for row in range(len(weights))
        for column in range(len(weights))
    )
    previous = cast(Sequence[float], request["previous_weights"])
    turnover = sum(abs(weight - previous[index]) for index, weight in enumerate(weights))
    active = [weight for weight in weights if weight > 1e-6]
    small = sum(weight < float(request["min_position"]) for weight in active)
    excess = max(len(active) - int(request["max_assets"]), 0)
    return (
        expected
        - 0.5 * float(request["risk_aversion"]) * variance
        - float(request["transaction_cost"]) * turnover
        - float(request["cardinality_penalty"]) * (small + excess)
    )


def _positive_semidefinite(matrix: Sequence[Sequence[float]]) -> bool:
    """Tolerant Cholesky test matching the qualified decision adapter boundary."""
    size = len(matrix)
    lower = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            subtotal = sum(lower[row][index] * lower[column][index] for index in range(column))
            if row == column:
                pivot = matrix[row][row] + 1e-10 - subtotal
                if pivot < 0:
                    return False
                lower[row][column] = math.sqrt(max(pivot, 0))
            elif lower[column][column] > 1e-15:
                lower[row][column] = (matrix[row][column] - subtotal) / lower[column][column]
            elif not math.isclose(matrix[row][column], subtotal, abs_tol=1e-10):
                return False
    return True


def _parse_timestamp(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CapitalPlanningError(f"{name} must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CapitalPlanningError(f"{name} must be an RFC3339 UTC timestamp") from exc
    _utc(parsed, name)
    return parsed


def _unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise CapitalPlanningError("capital snapshot contains duplicate JSON keys")
        result[key] = value
    return result


def _utc(value: object, name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise CapitalPlanningError(f"{name} must be timezone-aware UTC")


def _number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _bounded(value: object, minimum: float, maximum: float) -> bool:
    return _number(value) and minimum <= value <= maximum


def _integer(value: object, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise CapitalPlanningError("capital document is not canonical JSON") from exc


def _digest(value: object) -> str:
    return _digest_bytes(_canonical(value))


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
