"""Approval-bound warehouse recommendation workflow with downloadable evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from nexus_os.approval import ApprovalStore
from nexus_os.capabilities import RouteRequest
from nexus_os.domain import ActionEffect, RunId, TaskId, TraceId
from nexus_os.evidence import GENESIS, EvidenceKind, EvidenceLedger, EvidenceOutcome, EvidenceRecord
from nexus_os.node import NodePrincipal, RadNode
from nexus_os.warehouse_operations import (
    CAPABILITY_ID,
    OPERATION,
    VERSION,
    WarehouseOperationsEngine,
)


class WarehouseWorkflowError(ValueError):
    """Safe warehouse workflow rejection."""


@dataclass(frozen=True, slots=True)
class WarehousePlan:
    project_id: str
    run_id: RunId
    trace_id: TraceId
    request: Mapping[str, Any]
    engine_plan: Mapping[str, Any]
    plan_digest: str

    def canonical(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "workflow": "rad.operations.warehouse_allocation",
            "project_id": self.project_id,
            "run_id": str(self.run_id),
            "trace_id": str(self.trace_id),
            "request": dict(self.request),
            "engine_plan": dict(self.engine_plan),
            "approval_effect": ActionEffect.SENSITIVE.value,
        }


@dataclass(frozen=True, slots=True)
class WarehouseDossier:
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


def prepare_warehouse_plan(
    payload: bytes, *, project_id: str, run_id: RunId, trace_id: TraceId
) -> WarehousePlan:
    if not isinstance(project_id, str) or not project_id.strip() or len(project_id) > 256:
        raise WarehouseWorkflowError("project_id is invalid")
    engine = WarehouseOperationsEngine()
    try:
        request = engine.ingest(payload)
        engine_plan = engine.plan(request)
    except Exception as exc:
        raise WarehouseWorkflowError("warehouse snapshot is invalid") from exc
    draft = WarehousePlan(
        project_id,
        run_id,
        trace_id,
        MappingProxyType(request),
        MappingProxyType(engine_plan),
        "",
    )
    return WarehousePlan(
        project_id,
        run_id,
        trace_id,
        draft.request,
        draft.engine_plan,
        _digest(draft.canonical()),
    )


class WarehouseWorkflow:
    def __init__(self, node: RadNode, approvals: ApprovalStore, evidence: EvidenceLedger) -> None:
        if not isinstance(node, RadNode):
            raise WarehouseWorkflowError("RAD Node is required")
        self._node = node
        self._approvals = approvals
        self._evidence = evidence

    async def execute(
        self, plan: WarehousePlan, approval_id: UUID, principal: NodePrincipal, *, now: datetime
    ) -> WarehouseDossier:
        _utc(now)
        if _digest(plan.canonical()) != plan.plan_digest:
            raise WarehouseWorkflowError("warehouse plan digest is invalid")
        if self._evidence.records(plan.project_id, plan.run_id):
            raise WarehouseWorkflowError("warehouse run already contains evidence")
        try:
            approval = self._approvals.authorize_and_consume(
                approval_id,
                project_id=plan.project_id,
                run_id=plan.run_id,
                action_digest=plan.plan_digest,
                now=now,
            )
        except Exception as exc:
            raise WarehouseWorkflowError("exact warehouse plan approval is required") from exc
        route = RouteRequest(
            CAPABILITY_ID,
            OPERATION,
            frozenset({ActionEffect.READ_ONLY}),
            version=VERSION,
            max_timeout_seconds=30,
            max_memory_mib=1024,
        )
        try:
            execution = await self._node.execute(
                route,
                {"request": dict(plan.request), "plan_digest": plan.engine_plan["plan_digest"]},
                principal,
                at=now,
            )
        except Exception as exc:
            raise WarehouseWorkflowError("qualified warehouse execution failed") from exc
        result = dict(execution.output)
        if not WarehouseOperationsEngine().verify(plan.request, result):
            raise WarehouseWorkflowError("warehouse result failed acceptance verification")
        document = {
            "schema_version": "1.0",
            "workflow": "rad.operations.warehouse_allocation",
            "status": "VERIFIED_RECOMMENDATION_REQUIRES_WMS_ACTION_APPROVAL",
            "project_id": plan.project_id,
            "run_id": str(plan.run_id),
            "trace_id": str(plan.trace_id),
            "plan_digest": plan.plan_digest,
            "source_id": plan.request["source_id"],
            "engine": {
                "engine_id": result["engine_id"],
                "engine_version": result["engine_version"],
                "adapter_version": result["adapter_version"],
                "capability_id": result["capability_id"],
                "lease_id": str(execution.lease_id),
            },
            "recommendation": {
                "allocations": result["allocations"],
                "shortages": result["shortages"],
            },
            "expected_outcome": {
                "units_requested": result["units_requested"],
                "units_allocated": result["units_allocated"],
                "travel_unit_meters": result["travel_unit_meters"],
                "baseline_travel_unit_meters": result["baseline_travel_unit_meters"],
                "travel_savings_unit_meters": result["travel_savings_unit_meters"],
            },
            "acceptance": {
                "exact_plan_approved": True,
                "qualified_engine_routed": True,
                "allocation_verified": True,
                "external_execution_denied": result["external_write_authorized"] is False,
                "network_denied": result["network_used"] is False,
            },
            "execution_authorized": False,
            "required_approval": "separate_wms_action_approval",
            "limitations": sorted(set(result["limitations"] + ["operator_supplied_snapshot"])),
        }
        dossier_digest = _digest(document)
        count = self._append_evidence(plan, approval.decided_by or "unknown", dossier_digest, now)
        verified = self._evidence.verify(plan.project_id, plan.run_id)
        if verified.record_count != count:
            raise WarehouseWorkflowError("warehouse evidence scope contains unexpected records")
        return WarehouseDossier(
            MappingProxyType(document), dossier_digest, verified.head_hash, count
        )

    def export_evidence(self, dossier: WarehouseDossier) -> bytes:
        document = dossier.canonical()
        run_id = RunId.parse(document["run_id"])
        verified = self._evidence.verify(str(document["project_id"]), run_id)
        if (
            verified.head_hash != dossier.evidence_head
            or verified.record_count != dossier.evidence_count
            or _digest(dict(dossier.document)) != dossier.dossier_digest
        ):
            raise WarehouseWorkflowError("warehouse evidence export failed integrity verification")
        document["evidence"]["records"] = [
            item.to_dict() for item in self._evidence.records(str(document["project_id"]), run_id)
        ]
        return _canonical(document)

    def _append_evidence(
        self, plan: WarehousePlan, approver: str, dossier_digest: str, now: datetime
    ) -> int:
        specs = (
            (
                EvidenceKind.SPECIFICATION,
                "warehouse_plan",
                _digest(dict(plan.request)),
                plan.plan_digest,
            ),
            (EvidenceKind.APPROVAL, "warehouse_plan_approval", plan.plan_digest, plan.plan_digest),
            (EvidenceKind.TEST, "warehouse_acceptance", plan.plan_digest, dossier_digest),
            (EvidenceKind.ARTIFACT, "warehouse_dossier", plan.plan_digest, dossier_digest),
        )
        head = GENESIS
        for sequence, (kind, test_id, input_digest, output_digest) in enumerate(specs, start=1):
            actor = approver if kind is EvidenceKind.APPROVAL else "rad-operations"
            record = EvidenceRecord(
                uuid4(),
                sequence,
                now,
                plan.project_id,
                plan.run_id,
                TaskId("warehouse_review"),
                actor,
                "rad.operations.warehouse_allocation@1.0.0",
                kind,
                EvidenceOutcome.PASS,
                test_id,
                input_digest,
                output_digest,
                plan.trace_id,
                head,
            )
            head = self._evidence.append(record, expected_head=head).record_hash
        return len(specs)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise WarehouseWorkflowError("now must be timezone-aware UTC")
