"""Strict adapter for the qualified Financial Algorithm decision-support engine."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from nexus_os.capabilities import CapabilityKind, CapabilityManifest, NetworkAccess, ResourceLimits
from nexus_os.domain import ActionEffect

DecisionCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]
_OPERATIONS = frozenset({"portfolio.allocate", "valuation.estimate", "market.assess"})
_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "engine_id",
        "engine_version",
        "adapter_version",
        "capability_id",
        "request_digest",
        "operation",
        "decision",
        "execution_authorized",
        "limitations",
    }
)
_QUALIFICATION_DIGEST = "sha256:07cfa239eb43b657c87df2662db5861dfbb63557159ef0cf00d766eea40188dc"


class FinancialDecisionAdapterError(ValueError):
    """Safe financial decision adapter rejection."""


@dataclass(frozen=True, slots=True)
class FinancialDecisionIdentity:
    engine_id: str = "financial-algorithm"
    engine_version: str = "0.2.0"
    adapter_version: str = "1.0.0"
    capability_id: str = "rad.decision.financial"


@dataclass(frozen=True, slots=True)
class FinancialQualificationAttestation:
    report_digest: str
    case_count: int
    limitations: tuple[str, ...]


_SUPPORTED = FinancialDecisionIdentity()


def attest_financial_qualification(
    report: Mapping[str, Any],
) -> FinancialQualificationAttestation:
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
        raise FinancialDecisionAdapterError("financial qualification report is invalid")
    try:
        parsed = json.loads(json.dumps(report, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FinancialDecisionAdapterError("financial qualification report is invalid") from exc
    digest = _digest({key: value for key, value in parsed.items() if key != "report_digest"})
    expected = {
        "schema_version": "1.0",
        "engine_id": _SUPPORTED.engine_id,
        "engine_version": _SUPPORTED.engine_version,
        "adapter_version": _SUPPORTED.adapter_version,
        "capability_id": _SUPPORTED.capability_id,
        "qualification": "QUALIFIED_FOR_DECISION_SUPPORT_BENCHMARKS",
        "case_count": 25,
        "passed_count": 25,
        "report_digest": _QUALIFICATION_DIGEST,
    }
    cases, limitations = parsed.get("cases"), parsed.get("limitations")
    expected_ids = {
        f"decision-{seed}-{index}" for seed in (7, 19, 43, 101, 211) for index in range(5)
    }
    if (
        digest != _QUALIFICATION_DIGEST
        or any(parsed.get(key) != value for key, value in expected.items())
        or not isinstance(cases, list)
        or {case.get("case_id") for case in cases if isinstance(case, dict)} != expected_ids
        or any(
            not isinstance(case, dict)
            or case.get("outcome") != "PASS"
            or case.get("deterministic_replay") is not True
            or case.get("execution_authorized") is not False
            or case.get("operation") not in _OPERATIONS
            for case in cases
        )
        or not isinstance(limitations, list)
        or not limitations
        or not all(isinstance(item, str) and item for item in limitations)
    ):
        raise FinancialDecisionAdapterError("financial qualification report is not trusted")
    return FinancialQualificationAttestation(digest, len(cases), tuple(limitations))


class FinancialDecisionAdapter:
    def __init__(
        self,
        call: DecisionCall,
        qualification_report: Mapping[str, Any],
        identity: FinancialDecisionIdentity = _SUPPORTED,
    ) -> None:
        if not callable(call) or identity != _SUPPORTED:
            raise FinancialDecisionAdapterError("financial engine identity is unsupported")
        self.attestation = attest_financial_qualification(qualification_report)
        self.identity = identity
        self._call = call

    def manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id=self.identity.capability_id,
            version=self.identity.engine_version,
            kind=CapabilityKind.DOMAIN_PACK,
            description="Qualified, non-executing financial decision support.",
            operations=tuple(sorted(_OPERATIONS)),
            effects=frozenset({ActionEffect.READ_ONLY}),
            deterministic=True,
            network_access=NetworkAccess.DENIED,
            approval_required=True,
            qualification_required=True,
            resource_limits=ResourceLimits(300, 4096),
        )

    async def execute(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if operation not in _OPERATIONS:
            raise FinancialDecisionAdapterError("financial decision operation is unsupported")
        request = _request(operation, payload)
        try:
            value = await asyncio.to_thread(self._call, request)
        except Exception as exc:
            raise FinancialDecisionAdapterError(
                "financial decision engine execution failed"
            ) from exc
        return _result(value, request, self.identity)


def _request(operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or "operation" in payload:
        raise FinancialDecisionAdapterError("financial decision request is invalid")
    request = {"operation": operation, **dict(payload)}
    if operation == "portfolio.allocate":
        allowed = {
            "operation",
            "expected_returns",
            "covariance",
            "previous_weights",
            "risk_aversion",
            "transaction_cost",
            "cardinality_penalty",
            "min_position",
            "max_assets",
            "steps",
            "seed",
        }
        _allowed(request, allowed)
        returns = _numbers(
            request.get("expected_returns"), 2, 64, minimum_value=-5, maximum_value=5
        )
        covariance = request.get("covariance")
        if (
            not isinstance(covariance, Sequence)
            or isinstance(covariance, (str, bytes))
            or len(covariance) != len(returns)
        ):
            raise FinancialDecisionAdapterError("financial decision request is invalid")
        matrix = [
            _numbers(row, len(returns), len(returns), minimum_value=-25, maximum_value=25)
            for row in covariance
        ]
        if any(
            not math.isclose(matrix[row][column], matrix[column][row], abs_tol=1e-10)
            for row in range(len(matrix))
            for column in range(len(matrix))
        ) or not _positive_semidefinite(matrix):
            raise FinancialDecisionAdapterError("financial decision request is invalid")
        previous = _numbers(
            request.get("previous_weights", [1 / len(returns)] * len(returns)),
            len(returns),
            len(returns),
            minimum_value=0,
            maximum_value=1,
        )
        if not math.isclose(sum(previous), 1, abs_tol=1e-8):
            raise FinancialDecisionAdapterError("financial decision request is invalid")
        request = {
            "operation": operation,
            "expected_returns": returns,
            "covariance": matrix,
            "previous_weights": previous,
            "risk_aversion": _bounded_number(request.get("risk_aversion", 3.0), 0.01, 100),
            "transaction_cost": _bounded_number(request.get("transaction_cost", 0.01), 0, 1),
            "cardinality_penalty": _bounded_number(request.get("cardinality_penalty", 0.004), 0, 1),
            "min_position": _bounded_number(request.get("min_position", 0.08), 0, 1),
            "max_assets": _bounded_integer(
                request.get("max_assets", min(4, len(returns))), 1, len(returns)
            ),
            "steps": _bounded_integer(request.get("steps", 5000), 100, 100_000),
            "seed": _bounded_integer(request.get("seed", 7), 0, 2**32 - 1),
        }
    elif operation == "valuation.estimate":
        _allowed(
            request,
            {
                "operation",
                "cashflows",
                "discount_rate",
                "growth_mu",
                "growth_sigma",
                "simulations",
                "seed",
            },
        )
        request = {
            "operation": operation,
            "cashflows": _numbers(request.get("cashflows"), 2, 100, positive=True),
            "discount_rate": _bounded_number(request.get("discount_rate"), 0.0200000001, 10),
            "growth_mu": _bounded_number(request.get("growth_mu", 0.04), -0.99, 2),
            "growth_sigma": _bounded_number(request.get("growth_sigma", 0.08), 0, 2),
            "simulations": _bounded_integer(request.get("simulations", 10_000), 100, 100_000),
            "seed": _bounded_integer(request.get("seed", 7), 0, 2**32 - 1),
        }
    else:
        _allowed(request, {"operation", "prices", "window", "horizon", "neutral_band"})
        prices = _numbers(request.get("prices"), 20, 100_000, positive=True)
        request = {
            "operation": operation,
            "prices": prices,
            "window": _bounded_integer(request.get("window", 20), 20, min(5000, len(prices))),
            "horizon": _bounded_integer(request.get("horizon", 5), 1, 252),
            "neutral_band": _bounded_number(request.get("neutral_band", 0.05), 0, 0.49),
        }
    return request


def _result(
    value: Mapping[str, Any], request: dict[str, Any], identity: FinancialDecisionIdentity
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _RESULT_FIELDS:
        raise FinancialDecisionAdapterError("financial decision result contract is invalid")
    result = dict(value)
    expected = {
        "schema_version": "1.0",
        "engine_id": identity.engine_id,
        "engine_version": identity.engine_version,
        "adapter_version": identity.adapter_version,
        "capability_id": identity.capability_id,
        "request_digest": _digest(request),
        "operation": request["operation"],
        "execution_authorized": False,
    }
    limitations, decision = result.get("limitations"), result.get("decision")
    if (
        any(result.get(key) != item for key, item in expected.items())
        or not isinstance(decision, Mapping)
        or not decision
        or not _finite_tree(decision)
        or not isinstance(limitations, list)
        or not limitations
        or not all(isinstance(item, str) and item for item in limitations)
    ):
        raise FinancialDecisionAdapterError("financial decision result is invalid")
    return cast(dict[str, Any], json.loads(json.dumps(result, sort_keys=True, allow_nan=False)))


def _allowed(value: Mapping[str, Any], allowed: set[str]) -> None:
    if set(value) - allowed:
        raise FinancialDecisionAdapterError("financial decision request contains unknown fields")


def _numbers(
    value: object,
    minimum: int,
    maximum: int,
    *,
    positive: bool = False,
    minimum_value: float = -1e15,
    maximum_value: float = 1e15,
) -> list[float]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not minimum <= len(value) <= maximum
    ):
        raise FinancialDecisionAdapterError("financial decision request has invalid dimensions")
    lower = 1e-12 if positive else minimum_value
    numbers = [_bounded_number(item, lower, maximum_value) for item in value]
    return numbers


def _bounded_number(value: object, minimum: float, maximum: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise FinancialDecisionAdapterError("financial decision request is outside bounded limits")
    return float(value)


def _bounded_integer(value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise FinancialDecisionAdapterError("financial decision request is outside bounded limits")
    return value


def _finite_tree(value: object) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return not isinstance(value, bool) and math.isfinite(value)
    if isinstance(value, list):
        return all(_finite_tree(item) for item in value)
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _finite_tree(item) for key, item in value.items())
    return False


def _positive_semidefinite(matrix: list[list[float]]) -> bool:
    """Tolerant Cholesky test equivalent to accepting eigenvalues down to -1e-10."""
    size = len(matrix)
    lower = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            subtotal = sum(lower[row][index] * lower[column][index] for index in range(column))
            if row == column:
                pivot = matrix[row][row] + 1e-10 - subtotal
                if pivot < 0:
                    return False
                lower[row][column] = math.sqrt(max(pivot, 0))
            elif lower[column][column] > 1e-15:
                lower[row][column] = (matrix[row][column] - subtotal) / lower[column][column]
            elif not math.isclose(matrix[row][column], subtotal, abs_tol=1e-10):
                return False
    return True


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()
