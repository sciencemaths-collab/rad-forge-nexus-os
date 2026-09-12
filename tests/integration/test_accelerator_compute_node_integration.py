import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from vqpu.accelerator_engine import discover, execute, plan

from nexus_os.accelerator_compute_adapter import AppleGPUComputeAdapter
from nexus_os.capabilities import CapabilityRegistry, RouteRequest
from nexus_os.domain import ActionEffect
from nexus_os.node import NodePrincipal, NodeStore, RadNode
from nexus_os.qualification import CapabilityQualification, CapabilityState

NOW = datetime(2026, 9, 12, 16, tzinfo=UTC)
QUALIFICATION = json.loads(
    (Path(__file__).parents[1] / "fixtures/vqpu-apple-metal-qualification-0.6.0.json").read_text()
)


@pytest.mark.skipif(discover()["status"] != "AVAILABLE", reason="Apple Metal MLX unavailable")
def test_real_qualified_apple_gpu_executes_through_rad_node(tmp_path) -> None:
    adapter = AppleGPUComputeAdapter(execute, QUALIFICATION)
    qualification = CapabilityQualification(
        "rad.compute.apple_gpu",
        CapabilityState.QUALIFIED,
        "apple-metal-mlx-0.32.2",
        NOW,
        (),
        (),
    )
    store = NodeStore(tmp_path / "node.db", "apple-gpu-node")
    node = RadNode(store, CapabilityRegistry())
    node.bind(adapter.manifest(), adapter, adapter.execute, qualification, at=NOW)
    node.start(at=NOW)
    workload = {
        "workload_type": "linear_algebra.matmul.float32",
        "rows": 16,
        "inner": 16,
        "columns": 16,
        "seed": 19,
        "tolerance": 1e-5,
    }
    payload = {"workload": workload, "plan_digest": plan(workload)["plan_digest"]}
    route = RouteRequest(
        "rad.compute.apple_gpu",
        "compute.matmul",
        frozenset({ActionEffect.READ_ONLY}),
        version="0.6.0",
        max_timeout_seconds=300,
        max_memory_mib=4096,
    )
    principal = NodePrincipal("rad-runtime", frozenset({"node:execute", "node:read"}))
    completed = asyncio.run(node.execute(route, payload, principal, at=NOW))
    assert completed.output["device_class"] == "GPU"
    assert completed.output["runtime"] == "MLX"
    assert completed.output["fallback_used"] is False
    assert node.snapshot(principal).active_leases == 0
    store.close()
