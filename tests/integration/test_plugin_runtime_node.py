import asyncio

from nexus_os.capabilities import CapabilityRegistry, RouteRequest
from nexus_os.domain import ActionEffect
from nexus_os.node import NodePrincipal, NodeStore, RadNode
from nexus_os.plugin_runtime import WasmPluginAdapter
from tests.unit.test_plugin_runtime import NOW, activated, wasm_result


def test_qualified_wasm_plugin_routes_through_rad_node(tmp_path):
    plugin_store = activated(tmp_path, wasm_result({"decision": "review", "writes": False}))
    adapter = WasmPluginAdapter(plugin_store, "acme.warehouse", "1.2.3")
    node_store = NodeStore(tmp_path / "node.db", "plugin-node")
    node = RadNode(node_store, CapabilityRegistry())
    node.bind(adapter.manifest(), adapter, adapter.execute, adapter.qualification(), at=NOW)
    node.start(at=NOW)
    result = asyncio.run(
        node.execute(
            RouteRequest(
                "acme.warehouse.allocate",
                "warehouse.allocate",
                frozenset({ActionEffect.READ_ONLY}),
                version="1.0.0",
                max_timeout_seconds=30,
                max_memory_mib=1,
            ),
            {"units": 4},
            NodePrincipal("rad-runtime", frozenset({"node:execute", "node:read"})),
            at=NOW,
        )
    )
    assert result.output == {"decision": "review", "writes": False}
    plugin_store.close()
    node_store.close()
