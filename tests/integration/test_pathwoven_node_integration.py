import asyncio
from datetime import UTC, datetime

from nexus_os.capabilities import CapabilityRegistry, RouteRequest
from nexus_os.domain import ActionEffect
from nexus_os.node import NodePrincipal, NodeStore, RadNode
from nexus_os.optimization_adapter import PathWovenAdapter
from nexus_os.qualification import CapabilityQualification, CapabilityState
from tests.unit.test_optimization_adapter import QUALIFICATION, request, result

NOW = datetime(2026, 9, 12, 15, tzinfo=UTC)


def test_qualified_pathwoven_adapter_executes_through_rad_node(tmp_path) -> None:
    adapter = PathWovenAdapter(lambda value: result(value), QUALIFICATION)
    qualification = CapabilityQualification(
        "rad.optimization.pathwoven", CapabilityState.QUALIFIED, "pathwoven-0.2.0", NOW, (), ()
    )
    store = NodeStore(tmp_path / "node.db", "optimization-node")
    node = RadNode(store, CapabilityRegistry())
    node.bind(adapter.manifest(), adapter, adapter.execute, qualification, at=NOW)
    node.start(at=NOW)
    route = RouteRequest(
        "rad.optimization.pathwoven",
        "optimization.solve",
        frozenset({ActionEffect.READ_ONLY}),
        version="0.2.0",
        max_timeout_seconds=300,
        max_memory_mib=4096,
    )
    principal = NodePrincipal("rad-runtime", frozenset({"node:execute", "node:read"}))
    completed = asyncio.run(node.execute(route, request(), principal, at=NOW))
    assert completed.output["engine_id"] == "pathwoven-dcgo"
    assert completed.output["best_value"] == 0.05
    assert node.snapshot(principal).active_leases == 0
    store.close()
