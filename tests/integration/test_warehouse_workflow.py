import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from nexus_os.approval import ApprovalStatus, ApprovalStore
from nexus_os.capabilities import CapabilityRegistry
from nexus_os.domain import ActionEffect, RunId, TraceId
from nexus_os.evidence import EvidenceLedger
from nexus_os.node import NodePrincipal, NodeStore, RadNode
from nexus_os.qualification import CapabilityQualification, CapabilityState
from nexus_os.warehouse_operations import WarehouseOperationsEngine
from nexus_os.warehouse_workflow import (
    WarehouseWorkflow,
    WarehouseWorkflowError,
    prepare_warehouse_plan,
)

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


def _payload() -> bytes:
    return json.dumps(
        {
            "schema_version": "1.0",
            "source_id": "wms-export-42",
            "bins": [
                {"bin_id": "far", "sku": "A", "available_units": 10, "distance_meters": 80},
                {"bin_id": "near", "sku": "A", "available_units": 8, "distance_meters": 10},
            ],
            "orders": [
                {"order_id": "urgent", "sku": "A", "units": 12, "priority": 5},
                {"order_id": "normal", "sku": "A", "units": 2, "priority": 2},
            ],
        }
    ).encode()


def _system(tmp_path):
    engine = WarehouseOperationsEngine()
    node_store = NodeStore(tmp_path / "node.db", "warehouse-node")
    node = RadNode(node_store, CapabilityRegistry())
    qualification = CapabilityQualification(
        "rad.operations.warehouse",
        CapabilityState.QUALIFIED,
        "warehouse-1.0.0",
        NOW,
        (),
        (),
    )
    node.bind(engine.manifest(), engine, engine.execute, qualification, at=NOW)
    node.start(at=NOW)
    approvals = ApprovalStore(tmp_path / "approvals.db")
    evidence = EvidenceLedger(tmp_path / "evidence.db")
    return node, node_store, approvals, evidence


def test_approved_plan_runs_through_node_and_exports_verified_evidence(tmp_path):
    node, node_store, approvals, evidence = _system(tmp_path)
    run_id = RunId.parse("70000000-0000-4000-8000-000000000001")
    plan = prepare_warehouse_plan(
        _payload(), project_id="warehouse-2026", run_id=run_id, trace_id=TraceId("7" * 32)
    )
    approval_id = UUID("70000000-0000-4000-8000-000000000002")
    approvals.request(
        approval_id=approval_id,
        project_id=plan.project_id,
        run_id=run_id,
        action_digest=plan.plan_digest,
        effect=ActionEffect.SENSITIVE,
        requested_by="rad-operations",
        requested_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    approvals.decide(
        approval_id,
        status=ApprovalStatus.APPROVED,
        decided_by="warehouse-manager",
        decided_at=NOW,
    )
    workflow = WarehouseWorkflow(node, approvals, evidence)
    dossier = asyncio.run(
        workflow.execute(
            plan,
            approval_id,
            NodePrincipal("rad-runtime", frozenset({"node:execute", "node:read"})),
            now=NOW,
        )
    )
    exported = json.loads(workflow.export_evidence(dossier))
    assert dossier.document["status"] == "VERIFIED_RECOMMENDATION_REQUIRES_WMS_ACTION_APPROVAL"
    assert dossier.document["execution_authorized"] is False
    assert dossier.document["expected_outcome"]["travel_savings_unit_meters"] > 0
    assert all(dossier.document["acceptance"].values())
    assert exported["evidence"]["record_count"] == 4
    assert len(exported["evidence"]["records"]) == 4
    assert approvals.get(approval_id).status is ApprovalStatus.CONSUMED
    approvals.close()
    evidence.close()
    node_store.close()


def test_mismatched_approval_cannot_execute(tmp_path):
    node, node_store, approvals, evidence = _system(tmp_path)
    run_id = RunId.parse("70000000-0000-4000-8000-000000000003")
    plan = prepare_warehouse_plan(
        _payload(), project_id="warehouse-2026", run_id=run_id, trace_id=TraceId("8" * 32)
    )
    approval_id = UUID("70000000-0000-4000-8000-000000000004")
    approvals.request(
        approval_id=approval_id,
        project_id=plan.project_id,
        run_id=run_id,
        action_digest="sha256:" + "0" * 64,
        effect=ActionEffect.SENSITIVE,
        requested_by="rad-operations",
        requested_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    approvals.decide(
        approval_id, status=ApprovalStatus.APPROVED, decided_by="manager", decided_at=NOW
    )
    with pytest.raises(WarehouseWorkflowError, match="exact warehouse plan approval"):
        asyncio.run(
            WarehouseWorkflow(node, approvals, evidence).execute(
                plan,
                approval_id,
                NodePrincipal("rad-runtime", frozenset({"node:execute", "node:read"})),
                now=NOW,
            )
        )
    approvals.close()
    evidence.close()
    node_store.close()
