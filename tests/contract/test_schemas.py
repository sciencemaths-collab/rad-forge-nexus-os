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


def test_duplicate_agent_acceptance_identifier_is_rejected() -> None:
    candidate = contracts.load(ROOT / "examples/agent-candidate-specification.valid.json")
    candidate["acceptance_criteria"].append(dict(candidate["acceptance_criteria"][0]))
    with pytest.raises(ValueError, match="duplicate acceptance_id"):
        contracts.validate_candidate_semantics(candidate)


def test_review_ready_candidate_cannot_have_unresolved_questions() -> None:
    candidate = contracts.load(ROOT / "examples/agent-candidate-specification.valid.json")
    candidate["unresolved_questions"] = ["Which environment is authorized?"]
    with pytest.raises(ValueError, match="unresolved questions"):
        contracts.validate_candidate_semantics(candidate)


def test_illegal_agent_transition_is_rejected() -> None:
    session = contracts.load(ROOT / "examples/agent-session.valid.json")
    session["events"][1]["to_state"] = "RUNNING"
    session["events"][2]["from_state"] = "RUNNING"
    with pytest.raises(ValueError, match="illegal agent transition"):
        contracts.validate_agent_session_semantics(session)


def test_agent_session_history_must_match_current_state() -> None:
    session = contracts.load(ROOT / "examples/agent-session.valid.json")
    session["state"] = "COMPLETED"
    with pytest.raises(ValueError, match="current state"):
        contracts.validate_agent_session_semantics(session)


def test_privileged_model_use_requires_safety_evaluations() -> None:
    qualification = contracts.load(ROOT / "examples/model-qualification.valid.json")
    qualification["allowed_uses"].append("tool_selection")
    for evaluation in qualification["evaluations"]:
        if evaluation["category"] == "approval_boundary":
            evaluation["result"] = "FAIL"
    with pytest.raises(ValueError, match="privileged use"):
        contracts.validate_model_qualification_semantics(qualification)
