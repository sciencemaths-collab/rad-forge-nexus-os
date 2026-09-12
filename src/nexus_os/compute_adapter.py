"""Qualified RAD adapter for vQPU local CPU compute execution."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from nexus_os.capabilities import CapabilityKind, CapabilityManifest, NetworkAccess, ResourceLimits
from nexus_os.domain import ActionEffect

ComputeCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]
_DIGEST = "sha256:7e77ef3e4b4eb412b4b0a97bf39510857ad54fde7fc667f9c9345c54e51108b7"
_RESULT_FIELDS = {
    "schema_version",
    "engine_id",
    "engine_version",
    "adapter_version",
    "capability_id",
    "plan_digest",
    "workload_digest",
    "backend_id",
    "counts",
    "shots",
    "seed",
    "network_used",
    "cost_usd",
    "limitations",
    "result_digest",
}


class ComputeAdapterError(ValueError):
    """Safe compute adapter rejection."""


@dataclass(frozen=True, slots=True)
class ComputeQualificationAttestation:
    report_digest: str
    case_count: int
    limitations: tuple[str, ...]


def attest_compute_qualification(report: Mapping[str, Any]) -> ComputeQualificationAttestation:
    fields = {
        "schema_version",
        "engine_id",
        "engine_version",
        "adapter_version",
        "capability_id",
        "qualification",
        "case_count",
        "passed_count",
        "cases",
        "limitations",
        "report_digest",
    }
    if not isinstance(report, Mapping) or set(report) != fields:
        raise ComputeAdapterError("compute qualification report is invalid")
    parsed = json.loads(json.dumps(report, sort_keys=True, allow_nan=False))
    digest = _digest({key: value for key, value in parsed.items() if key != "report_digest"})
    expected = {
        "schema_version": "1.0",
        "engine_id": "rad-compute-engine",
        "engine_version": "0.5.0",
        "adapter_version": "1.0.0",
        "capability_id": "rad.compute.local",
        "qualification": "QUALIFIED_FOR_LOCAL_CPU_QUANTUM_SIMULATION",
        "case_count": 15,
        "passed_count": 15,
        "report_digest": _DIGEST,
    }
    cases, limitations = parsed.get("cases"), parsed.get("limitations")
    ids = {f"cpu-qsim-{seed}-{index}" for seed in (7, 19, 43, 101, 211) for index in range(3)}
    if (
        digest != _DIGEST
        or any(parsed.get(key) != value for key, value in expected.items())
        or not isinstance(cases, list)
        or {case.get("case_id") for case in cases if isinstance(case, dict)} != ids
        or any(
            not isinstance(case, dict)
            or case.get("outcome") != "PASS"
            or case.get("deterministic_replay") is not True
            or case.get("verified") is not True
            or case.get("backend_id") != "cpu.quantum_simulator"
            for case in cases
        )
        or not isinstance(limitations, list)
        or not limitations
    ):
        raise ComputeAdapterError("compute qualification report is not trusted")
    return ComputeQualificationAttestation(digest, len(cases), tuple(limitations))


class VQPUComputeAdapter:
    def __init__(self, call: ComputeCall, qualification_report: Mapping[str, Any]) -> None:
        if not callable(call):
            raise ComputeAdapterError("compute implementation is invalid")
        self.attestation = attest_compute_qualification(qualification_report)
        self._call = call

    def manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            "rad.compute.local",
            "0.5.0",
            CapabilityKind.ENGINE_OPERATION,
            "Qualified vQPU local CPU quantum simulation.",
            ("compute.execute",),
            frozenset({ActionEffect.READ_ONLY}),
            True,
            NetworkAccess.DENIED,
            True,
            True,
            ResourceLimits(300, 4096),
        )

    async def execute(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if operation != "compute.execute" or not isinstance(payload, Mapping):
            raise ComputeAdapterError("compute operation is unsupported")
        try:
            result = dict(await asyncio.to_thread(self._call, dict(payload)))
        except Exception as exc:
            raise ComputeAdapterError("compute execution failed") from exc
        if (
            set(result) != _RESULT_FIELDS
            or result.get("engine_id") != "rad-compute-engine"
            or result.get("engine_version") != "0.5.0"
            or result.get("adapter_version") != "1.0.0"
            or result.get("capability_id") != "rad.compute.local"
            or result.get("backend_id") != "cpu.quantum_simulator"
            or result.get("network_used") is not False
            or result.get("cost_usd") != 0.0
            or result.get("plan_digest") != payload.get("plan_digest")
            or not isinstance(result.get("counts"), Mapping)
            or not isinstance(result.get("shots"), int)
            or sum(result["counts"].values()) != result["shots"]
            or _digest({key: value for key, value in result.items() if key != "result_digest"})
            != result.get("result_digest")
        ):
            raise ComputeAdapterError("compute result is invalid")
        return cast(dict[str, Any], json.loads(json.dumps(result, sort_keys=True, allow_nan=False)))


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()
