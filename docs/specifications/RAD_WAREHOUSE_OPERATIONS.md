# RAD Warehouse Operations 1.0

Status: locally qualified bounded product kernel.

## Use case

Given an operator-exported snapshot of warehouse bins and priority order lines, RAD recommends
integer picks. Higher-priority orders receive available stock first; within each SKU, inventory
is drawn from the nearest bins. The dossier shows shortages, unit-distance cost, the input-order
baseline, and measured savings.

This is useful for pick-wave review, shortage triage, and testing allocation policy before a WMS
change. It is not a WMS, route planner, labor scheduler, replenishment engine, or autonomous
fulfilment system.

## Governed workflow

1. Ingest strict UTF-8 JSON with one source ID, 1–1,000 unique bins, and 1–1,000 unique orders.
2. Reject duplicate keys/identifiers, unknown fields, non-finite distances, invalid priorities,
   negative stock, oversized documents, and values outside declared bounds.
3. Prepare a SHA-256-bound plan containing the exact request, engine plan, capability, resource
   boundary, acceptance checks, and denied external-write state.
4. Consume a current one-use `SENSITIVE` approval for the exact project, run, and plan digest.
5. Route `warehouse.allocate` only to `rad.operations.warehouse@1.0.0` through RAD Node with
   network denied and 30-second/1,024-MiB limits.
6. Independently reproduce and verify every allocation, shortage, total, digest, identity, and
   baseline comparison.
7. Export a canonical dossier plus a verified four-record evidence chain.

Run the formal deterministic qualification:

```bash
uv run rad-warehouse-qualify --output artifacts/warehouse-qualification.json
```

Qualification is `QUALIFIED_FOR_BOUNDED_INTEGER_INVENTORY_ALLOCATION` only when all 15 cases
pass deterministic replay, independent verification, baseline comparison, and denied external
write. This gate is part of release evidence.

## Required snapshot

```json
{
  "schema_version": "1.0",
  "source_id": "wms-export-2026-09-12",
  "bins": [
    {"bin_id": "A-01", "sku": "SKU-1", "available_units": 40, "distance_meters": 12.5}
  ],
  "orders": [
    {"order_id": "ORDER-9", "sku": "SKU-1", "units": 8, "priority": 5}
  ]
}
```

## Exact boundary

The qualified algorithm is exact for its current separable policy: integer units, single-SKU
order lines, priority-first stock allocation, and linear distance cost with no coupling between
SKUs. It does not claim optimality for vehicle routing, batching, time windows, labor, capacity,
multi-stop paths, stochastic demand, or mixed business constraints.

Inputs are static operator-supplied snapshots; source authenticity and freshness are not proven.
Results are recommendation-only. No AWS, WMS, ERP, network, credential, or external-write adapter
is present. Such adapters stay unavailable until separately implemented, permission-reviewed,
benchmarked against real infrastructure, and qualified with an exact versioned attestation.
