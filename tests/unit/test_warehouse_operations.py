import asyncio
import copy
import json

import pytest

from nexus_os.warehouse_operations import WarehouseOperationsEngine, WarehouseOperationsError


def warehouse_request():
    return {
        "schema_version": "1.0",
        "source_id": "wms-export:dc-01",
        "bins": [
            {"bin_id": "far-a", "sku": "SKU-1", "available_units": 8, "distance_meters": 80},
            {"bin_id": "near-a", "sku": "SKU-1", "available_units": 6, "distance_meters": 10},
            {"bin_id": "near-b", "sku": "SKU-2", "available_units": 4, "distance_meters": 20},
        ],
        "orders": [
            {"order_id": "standard", "sku": "SKU-1", "units": 8, "priority": 2},
            {"order_id": "urgent", "sku": "SKU-1", "units": 8, "priority": 5},
            {"order_id": "missing", "sku": "SKU-2", "units": 6, "priority": 3},
        ],
    }


def test_plan_and_solution_are_deterministic_feasible_and_improve_baseline():
    engine = WarehouseOperationsEngine()
    request = warehouse_request()
    plan = engine.plan(request)
    first = engine.solve(request, plan_digest=plan["plan_digest"])
    second = engine.solve(request, plan_digest=plan["plan_digest"])
    assert first == second
    assert first["units_requested"] == 22
    assert first["units_allocated"] == 18
    assert first["shortages"] == [
        {"order_id": "missing", "sku": "SKU-2", "units": 2},
        {"order_id": "standard", "sku": "SKU-1", "units": 2},
    ]
    assert first["travel_unit_meters"] <= first["baseline_travel_unit_meters"]
    assert engine.verify(request, first)


def test_capability_is_approval_qualification_and_network_gated():
    manifest = WarehouseOperationsEngine().manifest()
    assert manifest.approval_required and manifest.qualification_required
    assert manifest.network_access.value == "DENIED"
    assert manifest.operations == ("warehouse.allocate",)


def test_async_capability_contract_executes_exact_plan():
    engine = WarehouseOperationsEngine()
    request = warehouse_request()
    plan = engine.plan(request)
    result = asyncio.run(
        engine.execute(
            "warehouse.allocate", {"request": request, "plan_digest": plan["plan_digest"]}
        )
    )
    assert result["external_write_authorized"] is False


@pytest.mark.parametrize(
    "mutation", ["duplicate_bin", "negative_stock", "bad_priority", "nan_distance"]
)
def test_invalid_and_unbounded_snapshots_fail_closed(mutation):
    value = copy.deepcopy(warehouse_request())
    if mutation == "duplicate_bin":
        value["bins"][1]["bin_id"] = value["bins"][0]["bin_id"]
    elif mutation == "negative_stock":
        value["bins"][0]["available_units"] = -1
    elif mutation == "bad_priority":
        value["orders"][0]["priority"] = 6
    else:
        value["bins"][0]["distance_meters"] = float("nan")
    with pytest.raises(WarehouseOperationsError):
        WarehouseOperationsEngine().plan(value)


def test_ingest_rejects_duplicate_json_keys_and_tampering():
    engine = WarehouseOperationsEngine()
    with pytest.raises(WarehouseOperationsError, match="strict UTF-8 JSON"):
        engine.ingest(b'{"schema_version":"1.0","schema_version":"1.0"}')
    request = warehouse_request()
    result = engine.solve(request, plan_digest=engine.plan(request)["plan_digest"])
    result["allocations"][0]["units"] += 1
    assert not engine.verify(request, result)


def test_ingested_snapshot_round_trips():
    engine = WarehouseOperationsEngine()
    assert engine.ingest(json.dumps(warehouse_request()).encode()) == warehouse_request()
