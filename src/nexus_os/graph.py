"""Deterministic compilation of task-graph wire payloads into domain values."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker

from nexus_os.domain import ActionEffect, DomainValidationError, TaskDefinition, TaskGraph, TaskId

MAX_GRAPH_BYTES = 4 * 1024 * 1024
_SOURCE_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "task-graph.schema.json"


class GraphCompileError(ValueError):
    """Safe, stable rejection of an invalid graph wire payload."""


class GraphValidationError(ValueError):
    """Safe rejection of graph dependency semantics."""


@dataclass(frozen=True, slots=True)
class ValidatedTaskGraph:
    """A graph paired with deterministic topological scheduling metadata."""

    graph: TaskGraph
    topological_order: tuple[TaskId, ...]
    levels: tuple[tuple[TaskId, ...], ...]


def validate_task_graph(graph: TaskGraph) -> ValidatedTaskGraph:
    """Validate dependency existence and acyclicity using deterministic Kahn traversal."""
    tasks = {task.task_id: task for task in graph.tasks}
    unknown = sorted(
        {
            dependency
            for task in graph.tasks
            for dependency in task.depends_on
            if dependency not in tasks
        },
        key=str,
    )
    if unknown:
        names = ", ".join(str(item) for item in unknown)
        raise GraphValidationError(f"unknown task dependencies: {names}")

    remaining = {task_id: set(task.depends_on) for task_id, task in tasks.items()}
    order: list[TaskId] = []
    levels: list[tuple[TaskId, ...]] = []
    while remaining:
        ready = tuple(sorted((task_id for task_id, deps in remaining.items() if not deps), key=str))
        if not ready:
            involved = ", ".join(sorted(str(task_id) for task_id in remaining))
            raise GraphValidationError(f"task graph contains a cycle involving: {involved}")
        levels.append(ready)
        order.extend(ready)
        ready_set = set(ready)
        remaining = {
            task_id: dependencies - ready_set
            for task_id, dependencies in remaining.items()
            if task_id not in ready_set
        }
    return ValidatedTaskGraph(graph=graph, topological_order=tuple(order), levels=tuple(levels))


def compile_task_graph(payload: Mapping[str, Any]) -> TaskGraph:
    """Compile a schema-valid graph payload without performing DAG semantics."""
    if not isinstance(payload, Mapping):
        raise GraphCompileError("task graph must be an object")
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise GraphCompileError("task graph must contain canonical JSON values") from exc
    if len(encoded.encode("utf-8")) > MAX_GRAPH_BYTES:
        raise GraphCompileError("task graph exceeds the 4 MiB compilation limit")

    validator = Draft202012Validator(_load_schema(), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "$"
        raise GraphCompileError(f"invalid task graph at {location}: {first.message}")

    try:
        tasks = tuple(_compile_task(cast(Mapping[str, Any], item)) for item in payload["tasks"])
        return TaskGraph(
            graph_id=UUID(cast(str, payload["graph_id"])),
            project_id=cast(str, payload["project_id"]),
            tasks=tasks,
            schema_version=cast(str, payload["schema_version"]),
        )
    except (DomainValidationError, ValueError, TypeError, KeyError) as exc:
        raise GraphCompileError(f"task graph domain compilation failed: {exc}") from exc


def _compile_task(payload: Mapping[str, Any]) -> TaskDefinition:
    retry = cast(Mapping[str, Any], payload["retry"])
    return TaskDefinition(
        task_id=TaskId(cast(str, payload["task_id"])),
        kind=cast(str, payload["kind"]),
        depends_on=tuple(TaskId(value) for value in cast(list[str], payload["depends_on"])),
        effect=ActionEffect(cast(str, payload["effect"])),
        timeout_seconds=cast(int, payload["timeout_seconds"]),
        max_attempts=cast(int, retry["max_attempts"]),
        backoff_seconds=cast(float, retry["backoff_seconds"]),
        input=cast(Mapping[str, Any], payload["input"]),
        acceptance_ids=tuple(cast(list[str], payload.get("acceptance_ids", []))),
    )


def _load_schema() -> Mapping[str, Any]:
    try:
        resource = files("nexus_os").joinpath("schemas/task-graph.schema.json")
        try:
            raw_schema = resource.read_text(encoding="utf-8")
        except OSError:
            raw_schema = _SOURCE_SCHEMA_PATH.read_text(encoding="utf-8")
        schema = cast(dict[str, Any], json.loads(raw_schema))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("packaged task-graph schema is unavailable or invalid") from exc
    Draft202012Validator.check_schema(schema)
    return schema
