"""Failure and scale-bound tests for graph semantic validation."""

from uuid import uuid4

from nexus_os.domain import ActionEffect, TaskDefinition, TaskGraph, TaskId
from nexus_os.graph import validate_task_graph


def test_long_valid_chain_is_iterative_and_does_not_recurse() -> None:
    tasks = []
    for index in range(1500):
        name = TaskId(f"task_{index:04d}")
        dependency = () if index == 0 else (TaskId(f"task_{index - 1:04d}"),)
        tasks.append(
            TaskDefinition(
                task_id=name,
                kind="test",
                depends_on=dependency,
                effect=ActionEffect.READ_ONLY,
                timeout_seconds=1,
                max_attempts=1,
                backoff_seconds=0,
                input={},
            )
        )
    graph = TaskGraph(graph_id=uuid4(), project_id="scale", tasks=tuple(reversed(tasks)))
    validated = validate_task_graph(graph)
    assert len(validated.topological_order) == 1500
    assert validated.topological_order[0] == TaskId("task_0000")
    assert validated.topological_order[-1] == TaskId("task_1499")
