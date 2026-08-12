from dataclasses import fields

from nexus_os.reference_workflow import ROW_COUNT, STAGES, WorkflowResult


def test_rw_100k_contract_is_fixed() -> None:
    assert ROW_COUNT == 100_000
    assert STAGES == (
        "import",
        "schema",
        "quality",
        "statistics",
        "chart",
        "explanation",
        "persistence",
    )
    assert {field.name for field in fields(WorkflowResult)} >= {
        "fixture_digest",
        "row_count",
        "statistics_digest",
        "evidence_head",
        "state_digest",
    }
