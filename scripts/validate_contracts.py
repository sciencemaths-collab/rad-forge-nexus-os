"""Validate NEXUS schemas, examples, and graph semantics deterministically."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

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
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(load(instance_path))


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


def main() -> None:
    for schema_path in sorted(SCHEMAS.glob("*.json")):
        Draft202012Validator.check_schema(load(schema_path))
    validate(ROOT / "examples/project.mock.yaml", "project.schema.json")
    graph_path = ROOT / "examples/task-graph.valid.json"
    validate(graph_path, "task-graph.schema.json")
    validate_graph_semantics(load(graph_path))
    print("All schema meta-validation, examples, and graph semantics passed.")


if __name__ == "__main__":
    main()

