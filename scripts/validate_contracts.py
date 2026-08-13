"""Validate NEXUS schemas, examples, and graph semantics deterministically."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        if path.suffix in {".yaml", ".yml"}:
            return yaml.safe_load(stream)
        return json.load(stream)


def validate(instance_path: Path, schema_name: str) -> None:
    schema = load(SCHEMAS / schema_name)
    Draft202012Validator.check_schema(schema)
    resources = []
    for path in sorted(SCHEMAS.glob("*.json")):
        local_schema = load(path)
        resources.append((local_schema["$id"], Resource.from_contents(local_schema)))
    registry = Registry().with_resources(resources)
    Draft202012Validator(schema, format_checker=FormatChecker(), registry=registry).validate(
        load(instance_path)
    )


def validate_graph_semantics(graph: dict[str, Any]) -> None:
    tasks = graph["tasks"]
    ids = [task["task_id"] for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task_id")
    known = set(ids)
    dependencies = {task["task_id"]: set(task["depends_on"]) for task in tasks}
    unknown = {dep for values in dependencies.values() for dep in values if dep not in known}
    if unknown:
        raise ValueError(f"unknown dependencies: {sorted(unknown)}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ValueError(f"task graph cycle at {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in dependencies[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in ids:
        visit(task_id)


AGENT_STATES = {
    "DRAFTING",
    "CLARIFICATION_REQUIRED",
    "SPECIFICATION_READY",
    "USER_REVIEW",
    "APPROVED",
    "RUNNING",
    "APPROVAL_REQUIRED",
    "VERIFYING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
}
AGENT_TRANSITIONS = {
    (None, "DRAFTING"),
    ("DRAFTING", "CLARIFICATION_REQUIRED"),
    ("CLARIFICATION_REQUIRED", "DRAFTING"),
    ("DRAFTING", "SPECIFICATION_READY"),
    ("SPECIFICATION_READY", "USER_REVIEW"),
    ("USER_REVIEW", "DRAFTING"),
    ("USER_REVIEW", "APPROVED"),
    ("USER_REVIEW", "CANCELLED"),
    ("APPROVED", "RUNNING"),
    ("RUNNING", "APPROVAL_REQUIRED"),
    ("RUNNING", "VERIFYING"),
    ("RUNNING", "FAILED"),
    ("RUNNING", "CANCELLED"),
    ("APPROVAL_REQUIRED", "RUNNING"),
    ("APPROVAL_REQUIRED", "FAILED"),
    ("APPROVAL_REQUIRED", "CANCELLED"),
    ("VERIFYING", "COMPLETED"),
    ("VERIFYING", "FAILED"),
}


def validate_candidate_semantics(candidate: dict[str, Any]) -> None:
    acceptance_ids = [item["acceptance_id"] for item in candidate["acceptance_criteria"]]
    if len(acceptance_ids) != len(set(acceptance_ids)):
        raise ValueError("duplicate acceptance_id")
    if candidate["review_ready"] and candidate["unresolved_questions"]:
        raise ValueError("review-ready candidate has unresolved questions")


def validate_agent_session_semantics(session: dict[str, Any]) -> None:
    events = session["events"]
    sequences = [event["sequence"] for event in events]
    if sequences != list(range(1, len(events) + 1)):
        raise ValueError("agent event sequence must be contiguous and start at 1")
    previous: str | None = None
    for event in events:
        if event["session_id"] != session["session_id"]:
            raise ValueError("agent event session mismatch")
        if event["from_state"] != previous:
            raise ValueError("agent event history state mismatch")
        transition = (event["from_state"], event["to_state"])
        if transition not in AGENT_TRANSITIONS:
            raise ValueError(f"illegal agent transition: {transition}")
        previous = event["to_state"]
    if previous != session["state"]:
        raise ValueError("agent current state does not match event history")


def validate_model_qualification_semantics(qualification: dict[str, Any]) -> None:
    categories = [item["category"] for item in qualification["evaluations"]]
    if (
        set(categories)
        != {
            "schema_conformance",
            "planning",
            "tool_selection",
            "approval_boundary",
            "evidence_grounding",
            "adversarial_input",
            "bounded_repair",
        }
        or len(categories) != 7
    ):
        raise ValueError("qualification must contain each required category exactly once")
    results = {item["category"]: item["result"] for item in qualification["evaluations"]}
    privileged = {"task_planning", "tool_selection", "repair_proposal", "sensitive_action_proposal"}
    if privileged.intersection(qualification["allowed_uses"]) and (
        results["approval_boundary"] != "PASS" or results["adversarial_input"] != "PASS"
    ):
        raise ValueError("privileged use requires approval and adversarial evaluation passes")


def main() -> None:
    for schema_path in sorted(SCHEMAS.glob("*.json")):
        Draft202012Validator.check_schema(load(schema_path))
    validate(ROOT / "examples/project.mock.yaml", "project.schema.json")
    graph_path = ROOT / "examples/task-graph.valid.json"
    validate(graph_path, "task-graph.schema.json")
    validate_graph_semantics(load(graph_path))
    candidate_path = ROOT / "examples/agent-candidate-specification.valid.json"
    validate(candidate_path, "agent-candidate-specification.schema.json")
    validate_candidate_semantics(load(candidate_path))
    session_path = ROOT / "examples/agent-session.valid.json"
    validate(session_path, "agent-session.schema.json")
    validate_agent_session_semantics(load(session_path))
    qualification_path = ROOT / "examples/model-qualification.valid.json"
    validate(qualification_path, "model-qualification.schema.json")
    validate_model_qualification_semantics(load(qualification_path))
    print("All schema meta-validation, examples, graph, and agent semantics passed.")


if __name__ == "__main__":
    main()
