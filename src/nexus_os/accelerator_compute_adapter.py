"""Qualified RAD adapter for real Apple Metal compute execution."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import struct
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from nexus_os.capabilities import CapabilityKind, CapabilityManifest, NetworkAccess, ResourceLimits
from nexus_os.domain import ActionEffect

AcceleratorCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]
QUALIFICATION_DIGEST = "sha256:c5a0c47229bf5c9217f00bb5e3d7ef0808e3498c78a1ef454c80795d685c7f68"
_RESULT_FIELDS = {
    "schema_version",
    "engine_id",
    "engine_version",
    "adapter_version",
    "capability_id",
    "backend_id",
    "plan_digest",
    "workload_digest",
    "shape",
    "dtype",
    "output",
    "output_bytes_digest",
    "maximum_absolute_reference_error",
    "tolerance",
    "reference_verified",
    "device_class",
    "runtime",
    "network_used",
    "cost_usd",
    "fallback_used",
    "limitations",
    "result_digest",
}


class AcceleratorComputeAdapterError(ValueError):
    """Safe accelerator adapter rejection."""


@dataclass(frozen=True, slots=True)
class AcceleratorQualificationAttestation:
    report_digest: str
    runtime_version: str
    case_count: int
    limitations: tuple[str, ...]


def attest_accelerator_qualification(
    report: Mapping[str, Any],
) -> AcceleratorQualificationAttestation:
    fields = {
        "schema_version",
        "engine_id",
        "engine_version",
        "adapter_version",
        "capability_id",
        "backend_id",
        "qualification",
        "case_count",
        "passed_count",
        "cases",
        "discovery",
        "limitations",
        "report_digest",
    }
    if not isinstance(report, Mapping) or set(report) != fields:
        raise AcceleratorComputeAdapterError("accelerator qualification report is invalid")
    try:
        parsed = json.loads(json.dumps(report, sort_keys=True, allow_nan=False))
        digest = _digest({key: value for key, value in parsed.items() if key != "report_digest"})
    except (TypeError, ValueError) as exc:
        raise AcceleratorComputeAdapterError("accelerator qualification report is invalid") from exc
    expected = {
        "schema_version": "1.0",
        "engine_id": "rad-compute-engine",
        "engine_version": "0.6.0",
        "adapter_version": "1.0.0",
        "capability_id": "rad.compute.apple_gpu",
        "backend_id": "apple.metal.mlx",
        "qualification": "QUALIFIED_FOR_APPLE_METAL_FLOAT32_MATMUL",
        "case_count": 15,
        "passed_count": 15,
        "report_digest": QUALIFICATION_DIGEST,
    }
    cases, discovery, limitations = (
        parsed.get("cases"),
        parsed.get("discovery"),
        parsed.get("limitations"),
    )
    ids = {
        f"apple-metal-matmul-{size}-s{seed}"
        for seed in (7, 19, 43, 101, 211)
        for size in (4, 16, 64)
    }
    if (
        digest != QUALIFICATION_DIGEST
        or any(parsed.get(key) != value for key, value in expected.items())
        or not isinstance(cases, list)
        or len(cases) != 15
        or {case.get("case_id") for case in cases if isinstance(case, dict)} != ids
        or any(
            not isinstance(case, dict)
            or case.get("outcome") != "PASS"
            or case.get("deterministic_replay") is not True
            or case.get("reference_verified") is not True
            or case.get("simulated") is not False
            or case.get("device_class") != "GPU"
            or case.get("runtime") != "MLX"
            or case.get("backend_id") != "apple.metal.mlx"
            for case in cases
        )
        or not isinstance(discovery, dict)
        or discovery.get("status") != "AVAILABLE"
        or discovery.get("runtime_version") != "0.32.2"
        or discovery.get("network_required") is not False
        or not isinstance(limitations, list)
        or not limitations
        or any(not isinstance(item, str) for item in limitations)
    ):
        raise AcceleratorComputeAdapterError("accelerator qualification report is not trusted")
    return AcceleratorQualificationAttestation(
        digest, discovery["runtime_version"], len(cases), tuple(limitations)
    )


class AppleGPUComputeAdapter:
    def __init__(self, call: AcceleratorCall, qualification_report: Mapping[str, Any]) -> None:
        if not callable(call):
            raise AcceleratorComputeAdapterError("accelerator implementation is invalid")
        self.attestation = attest_accelerator_qualification(qualification_report)
        self._call = call

    def manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            "rad.compute.apple_gpu",
            "0.6.0",
            CapabilityKind.ENGINE_OPERATION,
            "Qualified local Apple Metal float32 matrix multiplication via MLX 0.32.2.",
            ("compute.matmul",),
            frozenset({ActionEffect.READ_ONLY}),
            True,
            NetworkAccess.DENIED,
            True,
            True,
            ResourceLimits(300, 4096),
        )

    async def execute(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if operation != "compute.matmul" or not isinstance(payload, Mapping):
            raise AcceleratorComputeAdapterError("accelerator operation is unsupported")
        try:
            result = dict(await asyncio.to_thread(self._call, dict(payload)))
        except Exception as exc:
            raise AcceleratorComputeAdapterError("accelerator execution failed") from exc
        output, shape = result.get("output"), result.get("shape")
        output_digest = _matrix_digest(output) if _valid_matrix(output, shape) else None
        if (
            set(result) != _RESULT_FIELDS
            or result.get("engine_id") != "rad-compute-engine"
            or result.get("engine_version") != "0.6.0"
            or result.get("adapter_version") != "1.0.0"
            or result.get("capability_id") != "rad.compute.apple_gpu"
            or result.get("backend_id") != "apple.metal.mlx"
            or result.get("device_class") != "GPU"
            or result.get("runtime") != "MLX"
            or result.get("dtype") != "float32"
            or result.get("network_used") is not False
            or result.get("cost_usd") != 0.0
            or result.get("fallback_used") is not False
            or result.get("reference_verified") is not True
            or result.get("plan_digest") != payload.get("plan_digest")
            or not _valid_matrix(output, shape)
            or output_digest != result.get("output_bytes_digest")
            or not _finite(result.get("maximum_absolute_reference_error"))
            or not _finite(result.get("tolerance"))
            or result["maximum_absolute_reference_error"] > result["tolerance"]
            or _digest({key: value for key, value in result.items() if key != "result_digest"})
            != result.get("result_digest")
        ):
            raise AcceleratorComputeAdapterError("accelerator result is invalid")
        return cast(dict[str, Any], json.loads(json.dumps(result, sort_keys=True, allow_nan=False)))


def _valid_matrix(output: object, shape: object) -> bool:
    return (
        isinstance(shape, list)
        and len(shape) == 2
        and all(
            isinstance(item, int) and not isinstance(item, bool) and 1 <= item <= 256
            for item in shape
        )
        and isinstance(output, Sequence)
        and not isinstance(output, (str, bytes))
        and len(output) == shape[0]
        and all(
            isinstance(row, Sequence)
            and not isinstance(row, (str, bytes))
            and len(row) == shape[1]
            and all(_finite(value) for value in row)
            for row in output
        )
    )


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _matrix_digest(output: object) -> str | None:
    if not isinstance(output, Sequence) or isinstance(output, (str, bytes)):
        return None
    try:
        rows = cast(Sequence[Sequence[object]], output)
        values = [float(cast(int | float, value)) for row in rows for value in row]
        payload = struct.pack(f"={len(values)}f", *values)
    except (TypeError, ValueError, struct.error):
        return None
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()
