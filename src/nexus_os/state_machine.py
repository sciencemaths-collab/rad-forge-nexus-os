"""Deterministic, side-effect-free lifecycle enforcement for NEXUS runs and tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Final

from nexus_os.domain import Failure, RunId, RunState, TaskId, TaskStatus, TraceId

_REASON_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")

_RUN_TRANSITIONS: Final = MappingProxyType(
    {
        RunState.CREATED: frozenset({RunState.PLANNING, RunState.CANCELLING, RunState.FAILED}),
        RunState.PLANNING: frozenset({RunState.READY, RunState.CANCELLING, RunState.FAILED}),
        RunState.READY: frozenset({RunState.RUNNING, RunState.CANCELLING, RunState.FAILED}),
        RunState.RUNNING: frozenset(
            {RunState.PAUSED, RunState.CANCELLING, RunState.SUCCEEDED, RunState.FAILED}
        ),
        RunState.PAUSED: frozenset({RunState.RUNNING, RunState.CANCELLING, RunState.FAILED}),
        RunState.CANCELLING: frozenset({RunState.CANCELLED, RunState.FAILED}),
    }
)

_TASK_TRANSITIONS: Final = MappingProxyType(
    {
        TaskStatus.PENDING: frozenset(
            {
                TaskStatus.READY,
                TaskStatus.BLOCKED,
                TaskStatus.WAITING_APPROVAL,
                TaskStatus.CANCELLED,
                TaskStatus.SKIPPED,
            }
        ),
        TaskStatus.READY: frozenset(
            {
                TaskStatus.RUNNING,
                TaskStatus.BLOCKED,
                TaskStatus.WAITING_APPROVAL,
                TaskStatus.CANCELLED,
                TaskStatus.SKIPPED,
            }
        ),
        TaskStatus.RUNNING: frozenset(
            {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        ),
        TaskStatus.BLOCKED: frozenset(
            {
                TaskStatus.READY,
                TaskStatus.WAITING_APPROVAL,
                TaskStatus.CANCELLED,
                TaskStatus.SKIPPED,
            }
        ),
        TaskStatus.WAITING_APPROVAL: frozenset(
            {TaskStatus.READY, TaskStatus.CANCELLED, TaskStatus.SKIPPED}
        ),
    }
)


class StateTransitionError(ValueError):
    """Safe, stable error raised before an illegal transition can be persisted."""


@dataclass(frozen=True, slots=True)
class RunTransition:
    run_id: RunId
    source: RunState
    target: RunState
    sequence: int
    occurred_at: datetime
    trace_id: TraceId
    reason_code: str


@dataclass(frozen=True, slots=True)
class TaskTransition:
    run_id: RunId
    task_id: TaskId
    source: TaskStatus
    target: TaskStatus
    sequence: int
    occurred_at: datetime
    trace_id: TraceId
    reason_code: str
    failure: Failure | None = None


class StateMachine:
    """Validate lifecycle changes and return immutable transition records."""

    def can_transition_run(self, current: RunState, target: RunState) -> bool:
        return target in _RUN_TRANSITIONS.get(current, frozenset())

    def can_transition_task(self, current: TaskStatus, target: TaskStatus) -> bool:
        return target in _TASK_TRANSITIONS.get(current, frozenset())

    def transition_run(
        self,
        *,
        run_id: RunId,
        current: RunState,
        target: RunState,
        sequence: int,
        occurred_at: datetime,
        trace_id: TraceId,
        reason_code: str,
    ) -> RunTransition:
        _validate_common(sequence, occurred_at, reason_code)
        if current.is_terminal:
            raise StateTransitionError(f"terminal run state {current.value} cannot transition")
        if not self.can_transition_run(current, target):
            raise StateTransitionError(
                f"illegal run transition from {current.value} to {target.value}"
            )
        return RunTransition(
            run_id=run_id,
            source=current,
            target=target,
            sequence=sequence,
            occurred_at=occurred_at,
            trace_id=trace_id,
            reason_code=reason_code,
        )

    def transition_task(
        self,
        *,
        run_id: RunId,
        task_id: TaskId,
        current: TaskStatus,
        target: TaskStatus,
        sequence: int,
        occurred_at: datetime,
        trace_id: TraceId,
        reason_code: str,
        failure: Failure | None = None,
    ) -> TaskTransition:
        _validate_common(sequence, occurred_at, reason_code)
        if current.is_terminal:
            raise StateTransitionError(f"terminal task state {current.value} cannot transition")
        if not self.can_transition_task(current, target):
            raise StateTransitionError(
                f"illegal task transition from {current.value} to {target.value}"
            )
        if target is TaskStatus.FAILED and failure is None:
            raise StateTransitionError("FAILED task transition requires failure metadata")
        if target is not TaskStatus.FAILED and failure is not None:
            raise StateTransitionError("only FAILED task transition can carry failure metadata")
        return TaskTransition(
            run_id=run_id,
            task_id=task_id,
            source=current,
            target=target,
            sequence=sequence,
            occurred_at=occurred_at,
            trace_id=trace_id,
            reason_code=reason_code,
            failure=failure,
        )


def _validate_common(sequence: int, occurred_at: datetime, reason_code: str) -> None:
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise StateTransitionError("sequence must be a positive integer")
    if occurred_at.tzinfo is None or occurred_at.utcoffset() != UTC.utcoffset(occurred_at):
        raise StateTransitionError("occurred_at must be timezone-aware UTC")
    if not isinstance(reason_code, str) or not _REASON_PATTERN.fullmatch(reason_code):
        raise StateTransitionError("reason_code must be a bounded lowercase canonical token")
