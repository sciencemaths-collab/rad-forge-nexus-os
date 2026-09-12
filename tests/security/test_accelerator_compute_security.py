import asyncio
import copy
import json
from pathlib import Path

import pytest

from nexus_os.accelerator_compute_adapter import (
    AcceleratorComputeAdapterError,
    AppleGPUComputeAdapter,
)

QUALIFICATION = json.loads(
    (Path(__file__).parents[1] / "fixtures/vqpu-apple-metal-qualification-0.6.0.json").read_text()
)


def test_adapter_rejects_fallback_and_safe_error_hides_provider_details():
    def fallback(_payload):
        return {"fallback_used": True}

    with pytest.raises(AcceleratorComputeAdapterError, match="result is invalid"):
        asyncio.run(AppleGPUComputeAdapter(fallback, QUALIFICATION).execute("compute.matmul", {}))

    canary = "SECRET_PROVIDER_DETAIL"

    def failure(_payload):
        raise RuntimeError(canary)

    with pytest.raises(AcceleratorComputeAdapterError) as raised:
        asyncio.run(AppleGPUComputeAdapter(failure, QUALIFICATION).execute("compute.matmul", {}))
    assert canary not in str(raised.value)


def test_adapter_rejects_tampered_signed_result():
    result = {
        "schema_version": "1.0",
        "engine_id": "rad-compute-engine",
        "engine_version": "0.6.0",
        "adapter_version": "1.0.0",
        "capability_id": "rad.compute.apple_gpu",
        "backend_id": "apple.metal.mlx",
        "plan_digest": "sha256:" + "1" * 64,
        "workload_digest": "sha256:" + "2" * 64,
        "shape": [1, 1],
        "dtype": "float32",
        "output": [[1.0]],
        "output_bytes_digest": "sha256:" + "3" * 64,
        "maximum_absolute_reference_error": 0.0,
        "tolerance": 1e-5,
        "reference_verified": True,
        "device_class": "GPU",
        "runtime": "MLX",
        "network_used": False,
        "cost_usd": 0.0,
        "fallback_used": False,
        "limitations": ["apple_silicon_only"],
        "result_digest": "sha256:" + "4" * 64,
    }

    def tampered(_payload):
        changed = copy.deepcopy(result)
        changed["output"] = [[99.0]]
        return changed

    with pytest.raises(AcceleratorComputeAdapterError, match="result is invalid"):
        asyncio.run(
            AppleGPUComputeAdapter(tampered, QUALIFICATION).execute(
                "compute.matmul", {"plan_digest": result["plan_digest"]}
            )
        )
