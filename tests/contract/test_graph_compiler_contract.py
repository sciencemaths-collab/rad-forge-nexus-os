"""Contract tests for deterministic task-graph compilation."""

import json
from pathlib import Path

import pytest

from nexus_os.graph import GraphCompileError, compile_task_graph

ROOT = Path(__file__).parents[2]


def _valid_payload() -> dict[str, object]:
    return json.loads((ROOT / "examples/task-graph.valid.json").read_text())


def test_compiler_builds_canonical_domain_graph() -> None:
    graph = compile_task_graph(_valid_payload())
    assert graph.project_id == "rw_100k_demo"
    assert len(graph.tasks) == 2
    assert graph.digest.startswith("sha256:")


def test_compiler_applies_optional_acceptance_default() -> None:
    payload = _valid_payload()
    task = payload["tasks"][0]  # type: ignore[index]
    task.pop("acceptance_ids", None)  # type: ignore[union-attr]
    assert compile_task_graph(payload).tasks[0].acceptance_ids == ()


@pytest.mark.parametrize("field", ["graph_id", "project_id", "tasks"])
def test_compiler_rejects_missing_required_fields(field: str) -> None:
    payload = _valid_payload()
    payload.pop(field)
    with pytest.raises(GraphCompileError, match="invalid task graph"):
        compile_task_graph(payload)


def test_compiler_rejects_unknown_fields() -> None:
    payload = _valid_payload()
    payload["unexpected"] = True
    with pytest.raises(GraphCompileError, match="Additional properties"):
        compile_task_graph(payload)


def test_compiler_is_order_deterministic_but_defers_dependency_semantics() -> None:
    payload = _valid_payload()
    reverse = {**payload, "tasks": list(reversed(payload["tasks"]))}  # type: ignore[arg-type]
    assert compile_task_graph(payload).digest == compile_task_graph(reverse).digest

    first = payload["tasks"][0]  # type: ignore[index]
    first["depends_on"] = ["missing_task"]  # type: ignore[index]
    assert compile_task_graph(payload).tasks[0].depends_on
