"""Security and failure tests for runtime orchestration."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from nexus_os.domain import RunId, TaskId, TaskStatus, TraceId
from nexus_os.graph import compile_task_graph, validate_task_graph
from nexus_os.runtime import RuntimeOrchestrator, RuntimeOrchestratorError
from nexus_os.stores import CheckpointConflictError, SQLiteCheckpointStore

NOW = datetime(2026, 8, 12, 14, tzinfo=UTC)
TRACE = TraceId("2" * 32)


def _graph():  # type: ignore[no-untyped-def]
    return validate_task_graph(
        compile_task_graph(
            {
                "schema_version": "1.0",
                "graph_id": str(UUID("30000000-0000-4000-8000-000000000001")),
                "project_id": "security-test",
                "tasks": [{
                    "task_id": "task_a", "kind": "compute", "depends_on": [],
                    "effect": "READ_ONLY", "timeout_seconds": 30,
                    "retry": {"max_attempts": 1, "backoff_seconds": 0}, "input": {}
                }],
            }
        )
    )


def test_stale_snapshot_cannot_overwrite_newer_runtime_state(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with SQLiteCheckpointStore(tmp_path / "runtime.db") as store:
        runtime = RuntimeOrchestrator(store)
        stale = runtime.create(run_id=RunId.new(), graph=_graph(), trace_id=TRACE, now=NOW)
        runtime.start_task(stale, TaskId("task_a"), trace_id=TRACE, now=NOW)
        with pytest.raises(CheckpointConflictError):
            runtime.cancel(stale, trace_id=TRACE, now=NOW)


def test_nonterminal_completion_and_unknown_task_are_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with SQLiteCheckpointStore(tmp_path / "runtime.db") as store:
        runtime = RuntimeOrchestrator(store)
        snapshot = runtime.create(run_id=RunId.new(), graph=_graph(), trace_id=TRACE, now=NOW)
        with pytest.raises(RuntimeOrchestratorError, match="unknown task"):
            runtime.start_task(snapshot, TaskId("missing"), trace_id=TRACE, now=NOW)
        running = runtime.start_task(snapshot, TaskId("task_a"), trace_id=TRACE, now=NOW)
        with pytest.raises(RuntimeOrchestratorError, match="terminal completion"):
            runtime.complete_task(
                running, TaskId("task_a"), TaskStatus.RUNNING, trace_id=TRACE, now=NOW
            )
