import asyncio
import copy
import json
from pathlib import Path

import pytest
from vqpu.accelerator_engine import discover, execute, plan

from nexus_os.accelerator_compute_adapter import (
    AcceleratorComputeAdapterError,
    AppleGPUComputeAdapter,
)

QUALIFICATION = json.loads(
    (Path(__file__).parents[1] / "fixtures/vqpu-apple-metal-qualification-0.6.0.json").read_text()
)


def workload():
    return {
        "workload_type": "linear_algebra.matmul.float32",
        "rows": 4,
        "inner": 4,
        "columns": 4,
        "seed": 7,
        "tolerance": 1e-5,
    }


def test_manifest_is_local_deterministic_approval_and_qualification_gated():
    adapter = AppleGPUComputeAdapter(execute, QUALIFICATION)
    manifest = adapter.manifest()
    assert manifest.deterministic
    assert manifest.approval_required and manifest.qualification_required
    assert manifest.network_access.value == "DENIED"
    assert manifest.operations == ("compute.matmul",)
    assert adapter.attestation.runtime_version == "0.32.2"


@pytest.mark.skipif(discover()["status"] != "AVAILABLE", reason="Apple Metal MLX unavailable")
def test_real_apple_gpu_execution_crosses_the_rad_adapter():
    item = workload()
    payload = {"workload": item, "plan_digest": plan(item)["plan_digest"]}
    first = asyncio.run(
        AppleGPUComputeAdapter(execute, QUALIFICATION).execute("compute.matmul", payload)
    )
    second = asyncio.run(
        AppleGPUComputeAdapter(execute, QUALIFICATION).execute("compute.matmul", payload)
    )
    assert first == second
    assert first["device_class"] == "GPU"
    assert first["runtime"] == "MLX"
    assert first["fallback_used"] is False


def test_tampered_qualification_and_remote_operation_are_rejected():
    report = copy.deepcopy(QUALIFICATION)
    report["cases"][0]["simulated"] = True
    with pytest.raises(AcceleratorComputeAdapterError, match="not trusted"):
        AppleGPUComputeAdapter(execute, report)
    with pytest.raises(AcceleratorComputeAdapterError, match="unsupported"):
        asyncio.run(AppleGPUComputeAdapter(execute, QUALIFICATION).execute("cloud.submit", {}))
