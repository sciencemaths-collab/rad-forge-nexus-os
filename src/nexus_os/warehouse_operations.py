"""Deterministic, governed warehouse allocation capability."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Mapping
from typing import Any, TypeGuard, cast

from nexus_os.capabilities import CapabilityKind, CapabilityManifest, NetworkAccess, ResourceLimits
from nexus_os.domain import ActionEffect

CAPABILITY_ID = "rad.operations.warehouse"
VERSION = "1.0.0"
OPERATION = "warehouse.allocate"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,63}$")
_MAX_DOCUMENT_BYTES = 1_000_000
_MAX_BINS = 1_000
_MAX_ORDERS = 1_000
_MAX_UNITS = 1_000_000


class WarehouseOperationsError(ValueError):
    """Safe warehouse contract or verification rejection."""


class WarehouseOperationsEngine:
    """Allocate integer stock to priority orders with minimum unit-distance cost."""

    def manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            CAPABILITY_ID,
            VERSION,
            CapabilityKind.ENGINE_OPERATION,
            "Qualified integer inventory allocation for bounded warehouse snapshots.",
            (OPERATION,),
            frozenset({ActionEffect.READ_ONLY}),
            True,
            NetworkAccess.DENIED,
            True,
            True,
            ResourceLimits(30, 1024),
        )

    def ingest(self, payload: bytes) -> dict[str, Any]:
        if not isinstance(payload, bytes) or not 1 <= len(payload) <= _MAX_DOCUMENT_BYTES:
            raise WarehouseOperationsError("warehouse snapshot is empty or oversized")
        try:
            value = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeError, json.JSONDecodeError, WarehouseOperationsError) as exc:
            raise WarehouseOperationsError("warehouse snapshot is not strict UTF-8 JSON") from exc
        return _request(value)

    def plan(self, request: Mapping[str, Any]) -> dict[str, Any]:
        value = _request(request)
        unsigned = {
            "schema_version": "1.0",
            "capability_id": CAPABILITY_ID,
            "version": VERSION,
            "operation": OPERATION,
            "request_digest": _digest(value),
            "bin_count": len(value["bins"]),
            "order_count": len(value["orders"]),
            "maximum_allocated_units": sum(item["units"] for item in value["orders"]),
            "network_required": False,
            "external_write_authorized": False,
            "approval_required": True,
            "acceptance": [
                "integer_allocation_is_feasible",
                "higher_priority_shortages_are_avoided_when_stock_exists",
                "travel_cost_is_not_worse_than_input_order_baseline",
                "external_execution_is_denied",
            ],
        }
        return {**unsigned, "plan_digest": _digest(unsigned)}

    def solve(self, request: Mapping[str, Any], *, plan_digest: str) -> dict[str, Any]:
        value = _request(request)
        execution_plan = self.plan(value)
        if plan_digest != execution_plan["plan_digest"]:
            raise WarehouseOperationsError("warehouse plan digest mismatch")
        allocations, shortages = _allocate(value, nearest_first=True)
        baseline, _ = _allocate(value, nearest_first=False)
        travel = _travel(allocations)
        baseline_travel = _travel(baseline)
        unsigned = {
            "schema_version": "1.0",
            "engine_id": "rad-warehouse-operations",
            "engine_version": VERSION,
            "adapter_version": "1.0.0",
            "capability_id": CAPABILITY_ID,
            "operation": OPERATION,
            "plan_digest": plan_digest,
            "request_digest": execution_plan["request_digest"],
            "allocations": allocations,
            "shortages": shortages,
            "units_requested": sum(item["units"] for item in value["orders"]),
            "units_allocated": sum(item["units"] for item in allocations),
            "travel_unit_meters": travel,
            "baseline_travel_unit_meters": baseline_travel,
            "travel_savings_unit_meters": baseline_travel - travel,
            "network_used": False,
            "external_write_authorized": False,
            "limitations": [
                "single_sku_order_lines",
                "static_snapshot_only",
                "distance_cost_only",
                "recommendation_only",
            ],
        }
        result = {**unsigned, "result_digest": _digest(unsigned)}
        if not self.verify(value, result):
            raise WarehouseOperationsError("warehouse result failed internal verification")
        return result

    async def execute(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if operation != OPERATION or set(payload) != {"request", "plan_digest"}:
            raise WarehouseOperationsError("warehouse operation is unsupported")
        return self.solve(
            cast(Mapping[str, Any], payload["request"]),
            plan_digest=cast(str, payload["plan_digest"]),
        )

    def verify(self, request: Mapping[str, Any], result: Mapping[str, Any]) -> bool:
        try:
            value = _request(request)
            expected_allocations, expected_shortages = _allocate(value, nearest_first=True)
            unsigned = {key: item for key, item in result.items() if key != "result_digest"}
            return (
                result.get("engine_id") == "rad-warehouse-operations"
                and result.get("engine_version") == VERSION
                and result.get("adapter_version") == "1.0.0"
                and result.get("capability_id") == CAPABILITY_ID
                and result.get("operation") == OPERATION
                and result.get("plan_digest") == self.plan(value)["plan_digest"]
                and result.get("request_digest") == _digest(value)
                and result.get("allocations") == expected_allocations
                and result.get("shortages") == expected_shortages
                and result.get("units_allocated") == sum(x["units"] for x in expected_allocations)
                and result.get("units_requested") == sum(x["units"] for x in value["orders"])
                and result.get("travel_unit_meters") == _travel(expected_allocations)
                and _number(result.get("baseline_travel_unit_meters"))
                and result["travel_unit_meters"] <= result["baseline_travel_unit_meters"]
                and result.get("network_used") is False
                and result.get("external_write_authorized") is False
                and result.get("result_digest") == _digest(unsigned)
            )
        except (KeyError, TypeError, ValueError, WarehouseOperationsError):
            return False


def _request(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "source_id",
        "bins",
        "orders",
    }:
        raise WarehouseOperationsError("warehouse snapshot fields are invalid")
    if value.get("schema_version") != "1.0" or not _identifier(value.get("source_id")):
        raise WarehouseOperationsError("warehouse snapshot identity is invalid")
    bins, orders = value.get("bins"), value.get("orders")
    if not isinstance(bins, list) or not 1 <= len(bins) <= _MAX_BINS:
        raise WarehouseOperationsError("warehouse bins are invalid")
    if not isinstance(orders, list) or not 1 <= len(orders) <= _MAX_ORDERS:
        raise WarehouseOperationsError("warehouse orders are invalid")
    clean_bins = [_bin(item) for item in bins]
    clean_orders = [_order(item) for item in orders]
    if len({item["bin_id"] for item in clean_bins}) != len(clean_bins):
        raise WarehouseOperationsError("warehouse bin identifiers are duplicated")
    if len({item["order_id"] for item in clean_orders}) != len(clean_orders):
        raise WarehouseOperationsError("warehouse order identifiers are duplicated")
    return {
        "schema_version": "1.0",
        "source_id": value["source_id"],
        "bins": clean_bins,
        "orders": clean_orders,
    }


def _bin(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "bin_id",
        "sku",
        "available_units",
        "distance_meters",
    }:
        raise WarehouseOperationsError("warehouse bin fields are invalid")
    if not _identifier(value.get("bin_id")) or not _identifier(value.get("sku")):
        raise WarehouseOperationsError("warehouse bin identity is invalid")
    return {
        "bin_id": value["bin_id"],
        "sku": value["sku"],
        "available_units": _integer(value.get("available_units"), 0, _MAX_UNITS),
        "distance_meters": _bounded(value.get("distance_meters"), 0, 1_000_000),
    }


def _order(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"order_id", "sku", "units", "priority"}:
        raise WarehouseOperationsError("warehouse order fields are invalid")
    if not _identifier(value.get("order_id")) or not _identifier(value.get("sku")):
        raise WarehouseOperationsError("warehouse order identity is invalid")
    return {
        "order_id": value["order_id"],
        "sku": value["sku"],
        "units": _integer(value.get("units"), 1, _MAX_UNITS),
        "priority": _integer(value.get("priority"), 1, 5),
    }


def _allocate(
    request: Mapping[str, Any], *, nearest_first: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    remaining = {item["bin_id"]: item["available_units"] for item in request["bins"]}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in request["bins"]:
        grouped[item["sku"]].append(item)
    for bins in grouped.values():
        if nearest_first:
            bins.sort(key=lambda item: (item["distance_meters"], item["bin_id"]))
    allocations: list[dict[str, Any]] = []
    shortages: list[dict[str, Any]] = []
    orders = sorted(request["orders"], key=lambda item: (-item["priority"], item["order_id"]))
    for order in orders:
        needed = order["units"]
        for warehouse_bin in grouped.get(order["sku"], []):
            units = min(needed, remaining[warehouse_bin["bin_id"]])
            if units:
                allocations.append(
                    {
                        "order_id": order["order_id"],
                        "bin_id": warehouse_bin["bin_id"],
                        "sku": order["sku"],
                        "units": units,
                        "distance_meters": warehouse_bin["distance_meters"],
                    }
                )
                remaining[warehouse_bin["bin_id"]] -= units
                needed -= units
            if needed == 0:
                break
        if needed:
            shortages.append({"order_id": order["order_id"], "sku": order["sku"], "units": needed})
    return allocations, shortages


def _travel(allocations: list[dict[str, Any]]) -> float:
    return float(sum(item["units"] * item["distance_meters"] for item in allocations))


def _identifier(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _integer(value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise WarehouseOperationsError("warehouse integer is outside bounded limits")
    return value


def _bounded(value: object, minimum: float, maximum: float) -> float:
    if not _number(value) or not minimum <= value <= maximum:
        raise WarehouseOperationsError("warehouse number is outside bounded limits")
    return float(value)


def _number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WarehouseOperationsError("warehouse snapshot contains duplicate keys")
        result[key] = value
    return result


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()
