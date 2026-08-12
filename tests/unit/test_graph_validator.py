"""Unit tests for task-graph semantic validation and scheduling metadata."""

from uuid import uuid4

import pytest

from nexus_os.domain import ActionEffect, TaskDefinition, TaskGraph, TaskId
from nexus_os.graph import GraphValidationError, validate_task_graph


def test_validator_produces_stable_order_and_parallel_levels() -> None:
    graph = _graph(
        _task("publish", "analyze", "review"),
        _task("review", "load"),
        _task("analyze", "load"),
        _task("load"),
    )
    validated = validate_task_graph(graph)

    assert tuple(map(str, validated.topological_order)) == (
        "load",
        "analyze",
        "review",
        "publish",
    )
    assert tuple(tuple(map(str, level)) for level in validated.levels) == (
        ("load",),
        ("analyze", "review"),
        ("publish",),
    )


def test_validator_rejects_unknown_dependency() -> None:
    with pytest.raises(GraphValidationError, match="unknown task dependencies: missing"):
        validate_task_graph(_graph(_task("load", "missing")))


def test_validator_reports_all_unknown_dependencies_deterministically() -> None:
    with pytest.raises(GraphValidationError, match="missing_a, missing_z"):
        validate_task_graph(_graph(_task("load", "missing_z", "missing_a")))


def test_validator_rejects_two_node_and_longer_cycles() -> None:
    with pytest.raises(GraphValidationError, match="cycle involving: first, second"):
        validate_task_graph(_graph(_task("first", "second"), _task("second", "first")))
    with pytest.raises(GraphValidationError, match="cycle"):
        validate_task_graph(
            _graph(_task("first", "third"), _task("second", "first"), _task("third", "second"))
        )


def test_validator_does_not_mutate_or_replace_compiled_graph() -> None:
    graph = _graph(_task("second", "first"), _task("first"))
    validated = validate_task_graph(graph)
    assert validated.graph is graph
    assert graph.tasks[0].task_id == TaskId("second")


def _task(name: str, *dependencies: str) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(name),
        kind="test",
        depends_on=tuple(TaskId(item) for item in dependencies),
        effect=ActionEffect.READ_ONLY,
        timeout_seconds=1,
        max_attempts=1,
        backoff_seconds=0,
        input={},
    )


def _graph(*tasks: TaskDefinition) -> TaskGraph:
    return TaskGraph(graph_id=uuid4(), project_id="test", tasks=tasks)
