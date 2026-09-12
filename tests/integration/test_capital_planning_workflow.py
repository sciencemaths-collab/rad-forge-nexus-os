import asyncio
import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from financial_algorithms import decide

from nexus_os.approval import ApprovalStatus, ApprovalStore
from nexus_os.capabilities import CapabilityRegistry
from nexus_os.capital_planning import (
    CapitalPlanningWorkflow,
    ingest_capital_snapshot,
    prepare_capital_plan,
)
from nexus_os.domain import ActionEffect, RunId, TraceId
from nexus_os.evidence import EvidenceLedger
from nexus_os.financial_decision_adapter import FinancialDecisionAdapter
from nexus_os.node import NodePrincipal, NodeStore, RadNode
from nexus_os.qualification import CapabilityQualification, CapabilityState
from tests.unit.test_capital_planning import NOW, payload

QUALIFICATION = json.loads(
    (Path(__file__).parents[1] / "fixtures/financial-decision-qualification-0.2.0.json").read_text()
)


def test_real_engine_runs_approved_capital_plan_and_exports_verified_evidence(tmp_path):
    run_id = RunId.parse("60000000-0000-4000-8000-000000000001")
    trace_id = TraceId("66666666666666666666666666666666")
    adapter = FinancialDecisionAdapter(decide, QUALIFICATION)
    qualification = CapabilityQualification(
        "rad.decision.financial", CapabilityState.QUALIFIED, "financial-0.2.0", NOW, (), ()
    )
    node_store = NodeStore(tmp_path / "node.db", "capital-planning-node")
    node = RadNode(node_store, CapabilityRegistry())
    node.bind(adapter.manifest(), adapter, adapter.execute, qualification, at=NOW)
    node.start(at=NOW)
    approvals = ApprovalStore(tmp_path / "approvals.db")
    evidence = EvidenceLedger(tmp_path / "evidence.db")
    workflow = CapitalPlanningWorkflow(node, approvals, evidence)
    plan = prepare_capital_plan(
        ingest_capital_snapshot(payload(), now=NOW),
        project_id="capital-plan-2026",
        run_id=run_id,
        trace_id=trace_id,
    )
    approval_id = UUID("60000000-0000-4000-8000-000000000002")
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
        decided_by="capital-committee",
        decided_at=NOW,
    )

    dossier = asyncio.run(
        workflow.execute(
            plan,
            approval_id,
            NodePrincipal("rad-runtime", frozenset({"node:execute", "node:read"})),
            now=NOW,
        )
    )
    exported = json.loads(workflow.export_evidence(dossier))

    assert dossier.document["status"] == "VERIFIED_RECOMMENDATION_REQUIRES_EXTERNAL_ACTION_APPROVAL"
    assert dossier.document["execution_authorized"] is False
    assert dossier.document["engine"]["engine_id"] == "financial-algorithm"
    assert dossier.document["expected_outcome"]["utility_improvement"] >= -1e-12
    assert all(dossier.document["acceptance"].values())
    assert exported["evidence"]["record_count"] == 4
    assert len(exported["evidence"]["records"]) == 4
    assert approvals.get(approval_id).status is ApprovalStatus.CONSUMED
    approvals.close()
    evidence.close()
    node_store.close()
