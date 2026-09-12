import asyncio
import json
from pathlib import Path

import pytest
from vqpu.compute_engine import execute, plan

from nexus_os.compute_adapter import ComputeAdapterError, VQPUComputeAdapter

QUALIFICATION = json.loads(
    (Path(__file__).parents[1] / "fixtures/vqpu-compute-qualification-0.5.0.json").read_text()
)


def workload():
    return {
        "workload_type": "quantum.simulation",
        "qubits": 2,
        "shots": 128,
        "seed": 7,
        "gates": [{"name": "H", "targets": [0]}, {"name": "CNOT", "targets": [0, 1]}],
    }


def payload():
    value = workload()
    return {"workload": value, "plan_digest": plan(value)["plan_digest"]}


def test_manifest_is_approval_and_qualification_gated():
    manifest = VQPUComputeAdapter(execute, QUALIFICATION).manifest()
    assert manifest.approval_required and manifest.qualification_required
    assert manifest.network_access.value == "DENIED"
    assert manifest.operations == ("compute.execute",)


def test_real_vqpu_cpu_execution_is_verified_by_adapter():
    result = asyncio.run(
        VQPUComputeAdapter(execute, QUALIFICATION).execute("compute.execute", payload())
    )
    assert result["backend_id"] == "cpu.quantum_simulator"
    assert sum(result["counts"].values()) == 128


def test_tampered_qualification_and_remote_operation_are_rejected():
    report = dict(QUALIFICATION)
    report["report_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ComputeAdapterError):
        VQPUComputeAdapter(execute, report)
    with pytest.raises(ComputeAdapterError, match="unsupported"):
        asyncio.run(VQPUComputeAdapter(execute, QUALIFICATION).execute("qpu.submit", {}))
