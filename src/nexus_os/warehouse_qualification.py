"""Formal deterministic qualification for RAD Warehouse Operations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from nexus_os.warehouse_operations import WarehouseOperationsEngine


def qualify() -> dict[str, Any]:
    engine = WarehouseOperationsEngine()
    cases: list[dict[str, Any]] = []
    for seed in (7, 19, 43, 101, 211):
        for size in (4, 16, 64):
            request = _case(seed, size)
            plan = engine.plan(request)
            first = engine.solve(request, plan_digest=plan["plan_digest"])
            second = engine.solve(request, plan_digest=plan["plan_digest"])
            passed = (
                first == second
                and engine.verify(request, first)
                and first["travel_unit_meters"] <= first["baseline_travel_unit_meters"]
                and first["external_write_authorized"] is False
            )
            cases.append(
                {
                    "case_id": f"warehouse-b{size}-s{seed}",
                    "bin_count": size,
                    "order_count": size,
                    "outcome": "PASS" if passed else "FAIL",
                    "deterministic_replay": first == second,
                    "verified": engine.verify(request, first),
                    "baseline_not_worse": first["travel_unit_meters"]
                    <= first["baseline_travel_unit_meters"],
                    "external_write_authorized": first["external_write_authorized"],
                }
            )
    passed_count = sum(case["outcome"] == "PASS" for case in cases)
    unsigned = {
        "schema_version": "1.0",
        "engine_id": "rad-warehouse-operations",
        "engine_version": "1.0.0",
        "capability_id": "rad.operations.warehouse",
        "qualification": "QUALIFIED_FOR_BOUNDED_INTEGER_INVENTORY_ALLOCATION"
        if passed_count == len(cases)
        else "NOT_QUALIFIED",
        "case_count": len(cases),
        "passed_count": passed_count,
        "cases": cases,
        "limitations": [
            "single_sku_order_lines",
            "static_snapshot_only",
            "distance_cost_only",
            "recommendation_only",
        ],
    }
    return {**unsigned, "report_digest": _digest(unsigned)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Qualify RAD Warehouse Operations")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = qualify()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    if report["qualification"] == "NOT_QUALIFIED":
        raise SystemExit(2)


def _case(seed: int, size: int) -> dict[str, Any]:
    bins = [
        {
            "bin_id": f"bin-{index}",
            "sku": f"sku-{index % 4}",
            "available_units": 2 + (seed + index * 3) % 17,
            "distance_meters": float(5 + (seed * 11 + index * 29) % 300),
        }
        for index in range(size)
    ]
    orders = [
        {
            "order_id": f"order-{index}",
            "sku": f"sku-{index % 4}",
            "units": 1 + (seed * 3 + index * 7) % 13,
            "priority": 1 + (seed + index) % 5,
        }
        for index in range(size)
    ]
    return {
        "schema_version": "1.0",
        "source_id": f"qualification-{seed}-{size}",
        "bins": bins,
        "orders": orders,
    }


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    main()
