from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_contracts", ROOT / "scripts/validate_contracts.py"
)
assert SPEC and SPEC.loader
contracts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contracts)


def test_all_schemas_and_valid_examples() -> None:
    contracts.main()


def test_literal_provider_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        contracts.validate(
            ROOT / "tests/fixtures/project.invalid-secret.yaml", "project.schema.json"
        )


def test_unknown_dependency_is_rejected_semantically() -> None:
    path = ROOT / "tests/fixtures/task-graph.invalid-unknown-dependency.json"
    contracts.validate(path, "task-graph.schema.json")
    with pytest.raises(ValueError, match="unknown dependencies"):
        contracts.validate_graph_semantics(contracts.load(path))


def test_cycle_is_rejected_semantically() -> None:
    graph = {
        "tasks": [
            {"task_id": "a", "depends_on": ["b"]},
            {"task_id": "b", "depends_on": ["a"]},
        ]
    }
    with pytest.raises(ValueError, match="cycle"):
        contracts.validate_graph_semantics(graph)
