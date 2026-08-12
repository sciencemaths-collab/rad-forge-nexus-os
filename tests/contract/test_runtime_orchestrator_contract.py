"""Contract tests for deterministic runtime orchestration."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from nexus_os.domain import RunId, RunState, TaskId, TaskStatus, TraceId
from nexus_os.graph import compile_task_graph, validate_task_graph
from nexus_os.runtime import RuntimeOrchestrator, RuntimeOrchestratorError
from nexus_os.stores import SQLiteCheckpointStore

NOW = datetime(2026, 8, 12, 14, tzinfo=UTC)
TRACE = TraceId("1" * 32)


def _graph():  # type: ignore[no-untyped-def]
    return validate_task_graph(
        compile_task_graph(
            {
                "schema_version": "1.0",
                "graph_id": str(UUID("10000000-0000-4000-8000-000000000001")),
                "project_id": "runtime-test",
                "tasks": [
                    {
                        "task_id": "extract",
                        "kind": "compute",
                        "depends_on": [],
                        "effect": "READ_ONLY",
                        "timeout_seconds": 30,
                        "retry": {"max_attempts": 1, "backoff_seconds": 0},
                        "input": {},
                    },
                    {
                        "task_id": "report",
                        "kind": "compute",
                        "depends_on": ["extract"],
                        "effect": "WORKSPACE_WRITE",
                        "timeout_seconds": 30,
                        "retry": {"max_attempts": 1, "backoff_seconds": 0},
                        "input": {},
                    },
                ],
            }
        )
    )


def test_run_progress_is_durable_and_dependency_ordered(tmp_path) -> None:  # type: ignore[no-untyped-def]
    run_id = RunId.parse("20000000-0000-4000-8000-000000000001")
    path = tmp_path / "runtime.db"
    with SQLiteCheckpointStore(path) as store:
        runtime = RuntimeOrchestrator(store)
        created = runtime.create(run_id=run_id, graph=_graph(), trace_id=TRACE, now=NOW)
        assert created.run_state is RunState.READY
        assert created.task_states[TaskId("extract")] is TaskStatus.READY
        assert created.task_states[TaskId("report")] is TaskStatus.PENDING

        running = runtime.start_task(created, TaskId("extract"), trace_id=TRACE, now=NOW)
        completed = runtime.complete_task(
            running, TaskId("extract"), TaskStatus.SUCCEEDED, trace_id=TRACE, now=NOW
        )
        assert completed.task_states[TaskId("report")] is TaskStatus.READY

    with SQLiteCheckpointStore(path) as reopened:
        resumed = RuntimeOrchestrator(reopened).resume(run_id=run_id, graph=_graph())
        assert resumed == completed


def test_all_successful_tasks_complete_run(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with SQLiteCheckpointStore(tmp_path / "runtime.db") as store:
        runtime = RuntimeOrchestrator(store)
        snapshot = runtime.create(run_id=RunId.new(), graph=_graph(), trace_id=TRACE, now=NOW)
        for name in ("extract", "report"):
            task_id = TaskId(name)
            snapshot = runtime.start_task(snapshot, task_id, trace_id=TRACE, now=NOW)
            snapshot = runtime.complete_task(
                snapshot, task_id, TaskStatus.SUCCEEDED, trace_id=TRACE, now=NOW
            )
        assert snapshot.run_state is RunState.SUCCEEDED


def test_duplicate_or_out_of_order_dispatch_is_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with SQLiteCheckpointStore(tmp_path / "runtime.db") as store:
        runtime = RuntimeOrchestrator(store)
        snapshot = runtime.create(run_id=RunId.new(), graph=_graph(), trace_id=TRACE, now=NOW)
        with pytest.raises(RuntimeOrchestratorError, match="not READY"):
            runtime.start_task(snapshot, TaskId("report"), trace_id=TRACE, now=NOW)
        running = runtime.start_task(snapshot, TaskId("extract"), trace_id=TRACE, now=NOW)
        with pytest.raises(RuntimeOrchestratorError, match="not READY"):
            runtime.start_task(running, TaskId("extract"), trace_id=TRACE, now=NOW)


def test_cancellation_is_staged_and_durable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    run_id = RunId.new()
    with SQLiteCheckpointStore(tmp_path / "runtime.db") as store:
        runtime = RuntimeOrchestrator(store)
        snapshot = runtime.create(run_id=run_id, graph=_graph(), trace_id=TRACE, now=NOW)
        cancelled = runtime.cancel(snapshot, trace_id=TRACE, now=NOW)
        assert cancelled.run_state is RunState.CANCELLED
        assert set(cancelled.task_states.values()) == {TaskStatus.CANCELLED}
        assert store.load(run_id).payload["run_state"] == "CANCELLED"  # type: ignore[union-attr]


def test_resume_rejects_missing_or_terminal_checkpoint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with SQLiteCheckpointStore(tmp_path / "runtime.db") as store:
        runtime = RuntimeOrchestrator(store)
        with pytest.raises(RuntimeOrchestratorError, match="not found"):
            runtime.resume(run_id=RunId.new(), graph=_graph())
        snapshot = runtime.create(run_id=RunId.new(), graph=_graph(), trace_id=TRACE, now=NOW)
        terminal = runtime.cancel(snapshot, trace_id=TRACE, now=NOW)
        with pytest.raises(RuntimeOrchestratorError, match="terminal"):
            runtime.resume(run_id=terminal.run_id, graph=_graph())
