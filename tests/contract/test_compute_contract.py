from dataclasses import fields

from nexus_os.compute import ComputeArtifact, DeterministicCompute, Provenance


def test_compute_contract_exposes_required_operations_and_provenance() -> None:
    for operation in ("load_csv", "inspect_schema", "summarize", "select", "sort", "chart_inputs"):
        assert callable(getattr(DeterministicCompute, operation))
    assert {field.name for field in fields(Provenance)} == {
        "engine",
        "version",
        "input_digest",
        "parameters",
        "seed",
        "output_digest",
    }
    assert {field.name for field in fields(ComputeArtifact)} == {"operation", "value", "provenance"}
