import asyncio
from datetime import timedelta
from uuid import UUID

import pytest

from nexus_os.approval import ApprovalStatus, ApprovalStore
from nexus_os.capabilities import CapabilityRegistry
from nexus_os.capital_planning import (
    CapitalPlan,
    CapitalPlanningError,
    CapitalPlanningWorkflow,
    ingest_capital_snapshot,
    prepare_capital_plan,
)
from nexus_os.domain import ActionEffect, RunId, TraceId
from nexus_os.evidence import EvidenceLedger
from nexus_os.node import NodePrincipal, NodeStore, RadNode
from tests.unit.test_capital_planning import NOW, payload


def test_tampered_plan_is_rejected_before_routing(tmp_path):
    node_store = NodeStore(tmp_path / "node.db", "capital-security-node")
    node = RadNode(node_store, CapabilityRegistry())
    node.start(at=NOW)
    approvals = ApprovalStore(tmp_path / "approvals.db")
    evidence = EvidenceLedger(tmp_path / "evidence.db")
    workflow = CapitalPlanningWorkflow(node, approvals, evidence)
    run_id = RunId.parse("60000000-0000-4000-8000-000000000011")
    plan = prepare_capital_plan(
        ingest_capital_snapshot(payload(), now=NOW),
        project_id="capital-security",
        run_id=run_id,
        trace_id=TraceId("77777777777777777777777777777777"),
    )
    tampered = CapitalPlan(
        plan.project_id, plan.run_id, plan.trace_id, plan.snapshot, "sha256:" + "0" * 64
    )
    approval_id = UUID("60000000-0000-4000-8000-000000000012")
    approvals.request(
        approval_id=approval_id,
        project_id=plan.project_id,
        run_id=run_id,
        action_digest=tampered.plan_digest,
        effect=ActionEffect.SENSITIVE,
        requested_by="attacker",
        requested_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    approvals.decide(
        approval_id, status=ApprovalStatus.APPROVED, decided_by="attacker", decided_at=NOW
    )

    with pytest.raises(CapitalPlanningError, match="digest"):
        asyncio.run(
            workflow.execute(
                tampered,
                approval_id,
                NodePrincipal("rad-runtime", frozenset({"node:execute"})),
                now=NOW,
            )
        )
    assert approvals.get(approval_id).status is ApprovalStatus.APPROVED
    approvals.close()
    evidence.close()
    node_store.close()


def test_snapshot_rejects_secret_shaped_extra_fields():
    secret_payload = payload().replace(b'"schema_version": "1.0",', b'"api_key": "hidden",')
    with pytest.raises(CapitalPlanningError):
        ingest_capital_snapshot(secret_payload, now=NOW)
