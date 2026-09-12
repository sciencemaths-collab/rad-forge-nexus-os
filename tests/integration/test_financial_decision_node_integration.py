import asyncio
from datetime import UTC, datetime

from financial_algorithms import decide

from nexus_os.capabilities import CapabilityRegistry, RouteRequest
from nexus_os.domain import ActionEffect
from nexus_os.financial_decision_adapter import FinancialDecisionAdapter
from nexus_os.node import NodePrincipal, NodeStore, RadNode
from nexus_os.qualification import CapabilityQualification, CapabilityState
from tests.unit.test_financial_decision_adapter import QUALIFICATION, payload

NOW = datetime(2026, 9, 12, 16, tzinfo=UTC)


def test_real_qualified_financial_engine_executes_through_rad_node(tmp_path):
    adapter = FinancialDecisionAdapter(decide, QUALIFICATION)
    qualification = CapabilityQualification(
        "rad.decision.financial", CapabilityState.QUALIFIED, "financial-0.2.0", NOW, (), ()
    )
    store = NodeStore(tmp_path / "node.db", "financial-decision-node")
    node = RadNode(store, CapabilityRegistry())
    node.bind(adapter.manifest(), adapter, adapter.execute, qualification, at=NOW)
    node.start(at=NOW)
    route = RouteRequest(
        "rad.decision.financial",
        "market.assess",
        frozenset({ActionEffect.READ_ONLY}),
        version="0.2.0",
        max_timeout_seconds=300,
        max_memory_mib=4096,
    )
    principal = NodePrincipal("rad-runtime", frozenset({"node:execute", "node:read"}))
    completed = asyncio.run(node.execute(route, payload(), principal, at=NOW))
    assert completed.output["engine_id"] == "financial-algorithm"
    assert completed.output["execution_authorized"] is False
    assert completed.output["decision"]["signal"] == "POSITIVE"
    store.close()
