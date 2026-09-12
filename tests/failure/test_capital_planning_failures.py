import asyncio
from uuid import UUID

import pytest

from nexus_os.approval import ApprovalStore
from nexus_os.capabilities import CapabilityRegistry
from nexus_os.capital_planning import (
    CapitalPlanningError,
    CapitalPlanningWorkflow,
    ingest_capital_snapshot,
    prepare_capital_plan,
)
from nexus_os.domain import RunId, TraceId
from nexus_os.evidence import EvidenceLedger
from nexus_os.node import NodePrincipal, NodeStore, RadNode
from tests.unit.test_capital_planning import NOW, payload


def test_missing_approval_fails_without_evidence_or_engine_execution(tmp_path):
    node_store = NodeStore(tmp_path / "node.db", "capital-failure-node")
    node = RadNode(node_store, CapabilityRegistry())
    node.start(at=NOW)
    approvals = ApprovalStore(tmp_path / "approvals.db")
    evidence = EvidenceLedger(tmp_path / "evidence.db")
    workflow = CapitalPlanningWorkflow(node, approvals, evidence)
    run_id = RunId.parse("60000000-0000-4000-8000-000000000021")
    plan = prepare_capital_plan(
        ingest_capital_snapshot(payload(), now=NOW),
        project_id="capital-failure",
        run_id=run_id,
        trace_id=TraceId("88888888888888888888888888888888"),
    )

    with pytest.raises(CapitalPlanningError, match="approval"):
        asyncio.run(
            workflow.execute(
                plan,
                UUID("60000000-0000-4000-8000-000000000022"),
                NodePrincipal("rad-runtime", frozenset({"node:execute"})),
                now=NOW,
            )
        )
    assert evidence.records(plan.project_id, run_id) == ()
    approvals.close()
    evidence.close()
    node_store.close()
