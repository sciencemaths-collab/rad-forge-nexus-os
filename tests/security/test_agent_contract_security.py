from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_contracts_agent_security", ROOT / "scripts/validate_contracts.py"
)
assert SPEC and SPEC.loader
contracts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contracts)


def test_candidate_rejects_literal_secret_instead_of_artifact_reference(tmp_path: Path) -> None:
    candidate = contracts.load(ROOT / "examples/agent-candidate-specification.valid.json")
    candidate["inputs"] = ["sk-not-a-permitted-literal"]
    path = tmp_path / "candidate.json"
    path.write_text(__import__("json").dumps(candidate), encoding="utf-8")
    with pytest.raises(ValidationError):
        contracts.validate(path, "agent-candidate-specification.schema.json")


def test_agent_event_rejects_unknown_direct_execution_payload(tmp_path: Path) -> None:
    session = contracts.load(ROOT / "examples/agent-session.valid.json")
    session["events"][0]["tool_call"] = {"name": "shell", "input": "unsafe"}
    path = tmp_path / "session.json"
    path.write_text(__import__("json").dumps(session), encoding="utf-8")
    with pytest.raises(ValidationError):
        contracts.validate(path, "agent-session.schema.json")
