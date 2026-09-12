import json
from datetime import UTC, datetime

import pytest

from nexus_os.capital_planning import (
    CapitalPlanningError,
    ingest_capital_snapshot,
    prepare_capital_plan,
)
from nexus_os.domain import RunId, TraceId

NOW = datetime(2026, 9, 12, 18, tzinfo=UTC)


def snapshot_document():
    return {
        "schema_version": "1.0",
        "source_id": "approved-upload:planning-team",
        "observed_at": "2026-09-12T17:55:00Z",
        "valid_until": "2026-09-13T18:00:00Z",
        "asset_ids": ["factory-modernization", "inventory-buffer", "cash-reserve"],
        "expected_returns": [0.12, 0.08, 0.03],
        "covariance": [[0.04, 0.01, 0.0], [0.01, 0.025, 0.0], [0.0, 0.0, 0.002]],
        "previous_weights": [0.34, 0.33, 0.33],
        "policy": {
            "risk_aversion": 3.0,
            "transaction_cost": 0.01,
            "cardinality_penalty": 0.004,
            "min_position": 0.08,
            "max_assets": 3,
            "steps": 5000,
            "seed": 7,
        },
    }


def payload(document=None):
    return json.dumps(document or snapshot_document()).encode()


def test_ingest_and_plan_bind_source_engine_policy_and_acceptance():
    snapshot = ingest_capital_snapshot(payload(), now=NOW)
    plan = prepare_capital_plan(
        snapshot,
        project_id="capital-plan-2026",
        run_id=RunId.parse("60000000-0000-4000-8000-000000000001"),
        trace_id=TraceId("66666666666666666666666666666666"),
    )

    assert plan.snapshot.asset_ids == (
        "factory-modernization",
        "inventory-buffer",
        "cash-reserve",
    )
    assert plan.canonical()["engine_binding"] == {
        "capability_id": "rad.decision.financial",
        "version": "0.2.0",
        "operation": "portfolio.allocate",
        "network": "DENIED",
    }
    assert plan.plan_digest.startswith("sha256:")
    assert len(plan.canonical()["acceptance"]) == 5


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("valid_until", "2026-09-12T17:59:59Z", "currently valid"),
        ("asset_ids", ["same", "same"], "asset_ids"),
        ("previous_weights", [0.5, 0.3, 0.3], "sum to one"),
        (
            "covariance",
            [[0.04, 0.2, 0.0], [0.2, 0.025, 0.0], [0.0, 0.0, 0.002]],
            "positive semidefinite",
        ),
    ],
)
def test_invalid_snapshots_fail_closed(field, value, match):
    document = snapshot_document()
    document[field] = value
    if field == "asset_ids":
        document["expected_returns"] = document["expected_returns"][:2]
        document["covariance"] = [[0.04, 0.01], [0.01, 0.025]]
        document["previous_weights"] = [0.5, 0.5]
        document["policy"]["max_assets"] = 2
    with pytest.raises(CapitalPlanningError, match=match):
        ingest_capital_snapshot(payload(document), now=NOW)


def test_duplicate_json_keys_are_rejected():
    with pytest.raises(CapitalPlanningError, match="strict UTF-8 JSON"):
        ingest_capital_snapshot(b'{"schema_version":"1.0","schema_version":"1.0"}', now=NOW)
