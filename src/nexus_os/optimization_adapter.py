"""Strict adapter for the PathWoven-DCGO optimization engine contract."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from nexus_os.capabilities import (
    CapabilityKind,
    CapabilityManifest,
    NetworkAccess,
    ResourceLimits,
)
from nexus_os.domain import ActionEffect

EngineCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]
_OBJECTIVES = frozenset({"sphere", "rastrigin", "rosenbrock", "ackley", "michalewicz"})
_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "engine_id",
        "engine_version",
        "adapter_version",
        "capability_id",
        "request_digest",
        "objective",
        "best_x",
        "best_value",
        "evaluations",
        "iterations",
        "seed",
        "convergence",
        "limitations",
    }
)


class OptimizationAdapterError(ValueError):
    """Safe external optimization engine rejection."""


@dataclass(frozen=True, slots=True)
class PathWovenIdentity:
    engine_id: str = "pathwoven-dcgo"
    engine_version: str = "0.2.0"
    adapter_version: str = "1.0.0"
    capability_id: str = "rad.optimization.pathwoven"


_SUPPORTED_IDENTITY = PathWovenIdentity()
_QUALIFICATION_DIGEST = "sha256:71c5046cd1008e9da62065b6d36465d92c5c256004353897432a068d6e4c1c44"
_QUALIFICATION_FIELDS = frozenset(
    {
        "schema_version",
        "engine_id",
        "engine_version",
        "adapter_version",
        "capability_id",
        "qualification",
        "case_count",
        "passed_count",
        "max_evaluations_per_case",
        "cases",
        "limitations",
        "report_digest",
    }
)


@dataclass(frozen=True, slots=True)
class PathWovenQualificationAttestation:
    report_digest: str
    case_count: int
    limitations: tuple[str, ...]


def attest_pathwoven_qualification(
    report: Mapping[str, Any],
) -> PathWovenQualificationAttestation:
    """Verify the pinned formal qualification report before enabling the adapter."""
    if not isinstance(report, Mapping) or set(report) != _QUALIFICATION_FIELDS:
        raise OptimizationAdapterError("PathWoven qualification report is invalid")
    try:
        parsed = json.loads(json.dumps(report, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise OptimizationAdapterError("PathWoven qualification report is invalid") from exc
    unsigned = {key: value for key, value in parsed.items() if key != "report_digest"}
    digest = _digest(unsigned)
    identity = _SUPPORTED_IDENTITY
    expected_identity = {
        "schema_version": "1.0",
        "engine_id": identity.engine_id,
        "engine_version": identity.engine_version,
        "adapter_version": identity.adapter_version,
        "capability_id": identity.capability_id,
        "qualification": "QUALIFIED_FOR_BUILTIN_BENCHMARKS",
        "case_count": 50,
        "passed_count": 50,
        "max_evaluations_per_case": 1024,
        "report_digest": _QUALIFICATION_DIGEST,
    }
    if digest != _QUALIFICATION_DIGEST or any(
        parsed.get(key) != value for key, value in expected_identity.items()
    ):
        raise OptimizationAdapterError("PathWoven qualification report is not trusted")
    cases, limitations = parsed.get("cases"), parsed.get("limitations")
    expected_cases = {
        f"{objective}-d{dimensions}-s{seed}"
        for objective in _OBJECTIVES
        for dimensions in (2, 5)
        for seed in (7, 19, 43, 101, 211)
    }
    if (
        not isinstance(cases, list)
        or {case.get("case_id") for case in cases if isinstance(case, dict)} != expected_cases
        or any(
            not isinstance(case, dict)
            or case.get("outcome") != "PASS"
            or case.get("deterministic_replay") is not True
            or not isinstance(case.get("evaluations"), int)
            or not 1 <= case["evaluations"] <= 1024
            or not _numeric(case.get("best_value"))
            for case in cases
        )
        or not isinstance(limitations, list)
        or not limitations
        or not all(isinstance(item, str) and item for item in limitations)
    ):
        raise OptimizationAdapterError("PathWoven qualification cases are invalid")
    return PathWovenQualificationAttestation(digest, len(cases), tuple(limitations))


class PathWovenAdapter:
    def __init__(
        self,
        call: EngineCall,
        qualification_report: Mapping[str, Any],
        identity: PathWovenIdentity = _SUPPORTED_IDENTITY,
    ) -> None:
        if not callable(call) or identity != _SUPPORTED_IDENTITY:
            raise OptimizationAdapterError("PathWoven engine identity is unsupported")
        attestation = attest_pathwoven_qualification(qualification_report)
        self._call = call
        self.attestation = attestation
        self.identity = identity

    def manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id=self.identity.capability_id,
            version=self.identity.engine_version,
            kind=CapabilityKind.ENGINE_OPERATION,
            description="Bounded PathWoven-DCGO optimization over qualified built-in objectives.",
            operations=("optimization.solve",),
            effects=frozenset({ActionEffect.READ_ONLY}),
            deterministic=True,
            network_access=NetworkAccess.DENIED,
            approval_required=False,
            qualification_required=True,
            resource_limits=ResourceLimits(300, 4096),
        )

    async def execute(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if operation != "optimization.solve":
            raise OptimizationAdapterError("optimization operation is unsupported")
        request = _request(payload)
        try:
            result = await asyncio.to_thread(self._call, request)
        except Exception as exc:
            raise OptimizationAdapterError("PathWoven engine execution failed") from exc
        return _result(result, request, self.identity)


def _request(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "objective",
        "dimensions",
        "max_evaluations",
        "seed",
        "sectors",
        "particles_per_sector",
    }
    if not isinstance(value, Mapping) or set(value) - allowed:
        raise OptimizationAdapterError("optimization request is invalid")
    request = dict(value)
    request.setdefault("sectors", 8)
    request.setdefault("particles_per_sector", 4)
    bounds = {
        "dimensions": (2, 256),
        "max_evaluations": (100, 10_000_000),
        "seed": (0, 2**32 - 1),
        "sectors": (2, 256),
        "particles_per_sector": (2, 1024),
    }
    if request.get("objective") not in _OBJECTIVES:
        raise OptimizationAdapterError("optimization objective is unsupported")
    for name, (minimum, maximum) in bounds.items():
        item = request.get(name)
        if isinstance(item, bool) or not isinstance(item, int) or not minimum <= item <= maximum:
            raise OptimizationAdapterError("optimization request is outside bounded limits")
    if request["max_evaluations"] < request["sectors"] * request["particles_per_sector"] * 2:
        raise OptimizationAdapterError("optimization evaluation budget is insufficient")
    return request


def _result(
    value: Mapping[str, Any], request: dict[str, Any], identity: PathWovenIdentity
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _RESULT_FIELDS:
        raise OptimizationAdapterError("optimization result contract is invalid")
    result = dict(value)
    expected = {
        "schema_version": "1.0",
        "engine_id": identity.engine_id,
        "engine_version": identity.engine_version,
        "adapter_version": identity.adapter_version,
        "capability_id": identity.capability_id,
        "objective": request["objective"],
        "seed": request["seed"],
        "request_digest": _digest(request),
    }
    if any(result.get(key) != expected_value for key, expected_value in expected.items()):
        raise OptimizationAdapterError("optimization result identity binding is invalid")
    best_x, convergence = result.get("best_x"), result.get("convergence")
    if (
        not isinstance(best_x, list)
        or len(best_x) != request["dimensions"]
        or not all(_numeric(item) for item in best_x)
        or not _numeric(result.get("best_value"))
        or not isinstance(convergence, list)
        or not convergence
        or not all(_numeric(item) for item in convergence)
        or any(convergence[index] > convergence[index - 1] for index in range(1, len(convergence)))
        or not isinstance(result.get("evaluations"), int)
        or result["evaluations"] > request["max_evaluations"]
        or not isinstance(result.get("iterations"), int)
        or result["iterations"] != len(convergence)
        or not isinstance(result.get("limitations"), list)
        or not result["limitations"]
    ):
        raise OptimizationAdapterError("optimization result values are invalid")
    return cast(dict[str, Any], json.loads(json.dumps(result, sort_keys=True, allow_nan=False)))


def _digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _numeric(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
