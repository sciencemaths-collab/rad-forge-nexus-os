from nexus_os.capital_planning import ingest_capital_snapshot, prepare_capital_plan
from nexus_os.domain import RunId, TraceId
from tests.unit.test_capital_planning import NOW, payload


def test_plan_contract_has_exact_top_level_fields_and_stable_digest():
    snapshot = ingest_capital_snapshot(payload(), now=NOW)
    kwargs = {
        "project_id": "capital-plan-2026",
        "run_id": RunId.parse("60000000-0000-4000-8000-000000000001"),
        "trace_id": TraceId("66666666666666666666666666666666"),
    }
    first = prepare_capital_plan(snapshot, **kwargs)
    second = prepare_capital_plan(snapshot, **kwargs)

    assert set(first.canonical()) == {
        "schema_version",
        "workflow",
        "project_id",
        "run_id",
        "trace_id",
        "source",
        "asset_ids",
        "engine_request",
        "engine_binding",
        "approval_effect",
        "acceptance",
    }
    assert first.plan_digest == second.plan_digest
