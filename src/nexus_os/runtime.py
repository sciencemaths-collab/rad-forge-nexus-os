"""Deterministic runtime orchestration over validated graphs and durable checkpoints."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from nexus_os.domain import (
    Failure,
    RunId,
    RunState,
    TaskId,
    TaskStatus,
    TraceId,
)
from nexus_os.graph import ValidatedTaskGraph
from nexus_os.state_machine import StateMachine
from nexus_os.stores import SQLiteCheckpointStore


class RuntimeOrchestratorError(ValueError):
    """Safe orchestration failure raised before an invalid state can be persisted."""


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    """Immutable, revisioned runtime state for one validated graph."""

    run_id: RunId
    graph: ValidatedTaskGraph
    run_state: RunState
    task_states: Mapping[TaskId, TaskStatus]
    transition_sequence: int
    revision: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_states", MappingProxyType(dict(self.task_states)))


class RuntimeOrchestrator:
    """Coordinate lifecycle state and persist each accepted mutation with CAS."""

    def __init__(self, store: SQLiteCheckpointStore) -> None:
        self._store = store
        self._states = StateMachine()

    def create(
        self,
        *,
        run_id: RunId,
        graph: ValidatedTaskGraph,
        trace_id: TraceId,
        now: datetime,
    ) -> RuntimeSnapshot:
        sequence = 1
        self._states.transition_run(
            run_id=run_id,
            current=RunState.CREATED,
            target=RunState.PLANNING,
            sequence=sequence,
            occurred_at=now,
            trace_id=trace_id,
            reason_code="graph.validated",
        )
        sequence += 1
        self._states.transition_run(
            run_id=run_id,
            current=RunState.PLANNING,
            target=RunState.READY,
            sequence=sequence,
            occurred_at=now,
            trace_id=trace_id,
            reason_code="run.ready",
        )
        first_level = set(graph.levels[0])
        task_states = {
            task.task_id: (TaskStatus.READY if task.task_id in first_level else TaskStatus.PENDING)
            for task in graph.graph.tasks
        }
        snapshot = RuntimeSnapshot(
            run_id=run_id,
            graph=graph,
            run_state=RunState.READY,
            task_states=task_states,
            transition_sequence=sequence,
            revision=0,
        )
        return self._persist(snapshot, expected_revision=None, now=now)

    def resume(self, *, run_id: RunId, graph: ValidatedTaskGraph) -> RuntimeSnapshot:
        checkpoint = self._store.load(
            run_id,
            graph_digest=graph.graph.digest,
            schema_version=graph.graph.schema_version,
        )
        if checkpoint is None:
            raise RuntimeOrchestratorError("runtime checkpoint not found")
        try:
            run_state = RunState(checkpoint.payload["run_state"])
            raw_states = checkpoint.payload["task_states"]
            sequence = checkpoint.payload["transition_sequence"]
            if not isinstance(raw_states, dict) or not isinstance(sequence, int):
                raise ValueError
            expected_ids = {str(task.task_id) for task in graph.graph.tasks}
            if set(raw_states) != expected_ids:
                raise ValueError
            task_states = {TaskId(key): TaskStatus(value) for key, value in raw_states.items()}
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeOrchestratorError("runtime checkpoint payload is invalid") from exc
        if run_state.is_terminal:
            raise RuntimeOrchestratorError("terminal runtime checkpoint cannot be resumed")
        return RuntimeSnapshot(
            run_id=run_id,
            graph=graph,
            run_state=run_state,
            task_states=task_states,
            transition_sequence=sequence,
            revision=checkpoint.revision,
        )

    def start_task(
        self,
        snapshot: RuntimeSnapshot,
        task_id: TaskId,
        *,
        trace_id: TraceId,
        now: datetime,
    ) -> RuntimeSnapshot:
        current = self._task_state(snapshot, task_id)
        if current is not TaskStatus.READY:
            raise RuntimeOrchestratorError(f"task {task_id} is not READY")
        sequence = snapshot.transition_sequence + 1
        self._states.transition_task(
            run_id=snapshot.run_id,
            task_id=task_id,
            current=current,
            target=TaskStatus.RUNNING,
            sequence=sequence,
            occurred_at=now,
            trace_id=trace_id,
            reason_code="task.dispatched",
        )
        run_state = snapshot.run_state
        if run_state is RunState.READY:
            sequence += 1
            self._states.transition_run(
                run_id=snapshot.run_id,
                current=run_state,
                target=RunState.RUNNING,
                sequence=sequence,
                occurred_at=now,
                trace_id=trace_id,
                reason_code="task.started",
            )
            run_state = RunState.RUNNING
        task_states = dict(snapshot.task_states)
        task_states[task_id] = TaskStatus.RUNNING
        return self._persist(
            RuntimeSnapshot(
                snapshot.run_id,
                snapshot.graph,
                run_state,
                task_states,
                sequence,
                snapshot.revision,
            ),
            expected_revision=snapshot.revision,
            now=now,
        )

    def complete_task(
        self,
        snapshot: RuntimeSnapshot,
        task_id: TaskId,
        status: TaskStatus,
        *,
        trace_id: TraceId,
        now: datetime,
        failure: Failure | None = None,
    ) -> RuntimeSnapshot:
        if not status.is_terminal:
            raise RuntimeOrchestratorError("task completion requires a terminal completion status")
        current = self._task_state(snapshot, task_id)
        if current is not TaskStatus.RUNNING:
            raise RuntimeOrchestratorError(f"task {task_id} is not RUNNING")
        sequence = snapshot.transition_sequence + 1
        self._states.transition_task(
            run_id=snapshot.run_id,
            task_id=task_id,
            current=current,
            target=status,
            sequence=sequence,
            occurred_at=now,
            trace_id=trace_id,
            reason_code=f"task.{status.value.lower()}",
            failure=failure,
        )
        task_states = dict(snapshot.task_states)
        task_states[task_id] = status
        self._unlock_dependents(snapshot.graph, task_states)
        run_state = snapshot.run_state
        if all(value is TaskStatus.SUCCEEDED for value in task_states.values()):
            sequence += 1
            self._states.transition_run(
                run_id=snapshot.run_id,
                current=run_state,
                target=RunState.SUCCEEDED,
                sequence=sequence,
                occurred_at=now,
                trace_id=trace_id,
                reason_code="run.succeeded",
            )
            run_state = RunState.SUCCEEDED
        return self._persist(
            RuntimeSnapshot(
                snapshot.run_id,
                snapshot.graph,
                run_state,
                task_states,
                sequence,
                snapshot.revision,
            ),
            expected_revision=snapshot.revision,
            now=now,
        )

    def cancel(
        self,
        snapshot: RuntimeSnapshot,
        *,
        trace_id: TraceId,
        now: datetime,
    ) -> RuntimeSnapshot:
        if snapshot.run_state.is_terminal:
            raise RuntimeOrchestratorError("terminal runtime cannot be cancelled")
        sequence = snapshot.transition_sequence + 1
        self._states.transition_run(
            run_id=snapshot.run_id,
            current=snapshot.run_state,
            target=RunState.CANCELLING,
            sequence=sequence,
            occurred_at=now,
            trace_id=trace_id,
            reason_code="cancel.requested",
        )
        task_states = dict(snapshot.task_states)
        for task_id in sorted(task_states, key=str):
            current = task_states[task_id]
            if current.is_terminal:
                continue
            sequence += 1
            self._states.transition_task(
                run_id=snapshot.run_id,
                task_id=task_id,
                current=current,
                target=TaskStatus.CANCELLED,
                sequence=sequence,
                occurred_at=now,
                trace_id=trace_id,
                reason_code="cancel.confirmed",
            )
            task_states[task_id] = TaskStatus.CANCELLED
        sequence += 1
        self._states.transition_run(
            run_id=snapshot.run_id,
            current=RunState.CANCELLING,
            target=RunState.CANCELLED,
            sequence=sequence,
            occurred_at=now,
            trace_id=trace_id,
            reason_code="cancel.confirmed",
        )
        return self._persist(
            RuntimeSnapshot(
                snapshot.run_id,
                snapshot.graph,
                RunState.CANCELLED,
                task_states,
                sequence,
                snapshot.revision,
            ),
            expected_revision=snapshot.revision,
            now=now,
        )

    @staticmethod
    def _task_state(snapshot: RuntimeSnapshot, task_id: TaskId) -> TaskStatus:
        try:
            return snapshot.task_states[task_id]
        except KeyError as exc:
            raise RuntimeOrchestratorError(f"unknown task {task_id}") from exc

    @staticmethod
    def _unlock_dependents(
        graph: ValidatedTaskGraph, task_states: dict[TaskId, TaskStatus]
    ) -> None:
        tasks = {task.task_id: task for task in graph.graph.tasks}
        for task_id in graph.topological_order:
            if task_states[task_id] is not TaskStatus.PENDING:
                continue
            if all(task_states[item] is TaskStatus.SUCCEEDED for item in tasks[task_id].depends_on):
                task_states[task_id] = TaskStatus.READY

    def _persist(
        self,
        snapshot: RuntimeSnapshot,
        *,
        expected_revision: int | None,
        now: datetime,
    ) -> RuntimeSnapshot:
        checkpoint = self._store.save(
            run_id=snapshot.run_id,
            graph_digest=snapshot.graph.graph.digest,
            schema_version=snapshot.graph.graph.schema_version,
            payload={
                "run_state": snapshot.run_state.value,
                "task_states": {
                    str(key): value.value
                    for key, value in sorted(
                        snapshot.task_states.items(), key=lambda item: str(item[0])
                    )
                },
                "transition_sequence": snapshot.transition_sequence,
            },
            expected_revision=expected_revision,
            saved_at=now,
        )
        return RuntimeSnapshot(
            run_id=snapshot.run_id,
            graph=snapshot.graph,
            run_state=snapshot.run_state,
            task_states=snapshot.task_states,
            transition_sequence=snapshot.transition_sequence,
            revision=checkpoint.revision,
        )
