"""Failure and abuse tests for lifecycle enforcement."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from nexus_os.domain import RunId, RunState, TaskId, TaskStatus, TraceId
from nexus_os.state_machine import StateMachine, StateTransitionError


@pytest.mark.parametrize("sequence", [0, -1, True])
def test_transition_sequence_must_be_positive_integer(sequence: object) -> None:
    with pytest.raises(StateTransitionError, match="sequence"):
        StateMachine().transition_run(
            run_id=RunId.new(),
            current=RunState.CREATED,
            target=RunState.PLANNING,
            sequence=sequence,  # type: ignore[arg-type]
            occurred_at=datetime(2026, 8, 12, tzinfo=UTC),
            trace_id=TraceId("0123456789abcdef0123456789abcdef"),
            reason_code="test",
        )


@pytest.mark.parametrize(
    "occurred_at",
    [datetime(2026, 8, 12), datetime(2026, 8, 12, tzinfo=timezone(timedelta(hours=1)))],
)
def test_transition_time_must_be_utc(occurred_at: datetime) -> None:
    with pytest.raises(StateTransitionError, match="UTC"):
        StateMachine().transition_task(
            run_id=RunId.new(),
            task_id=TaskId("task_one"),
            current=TaskStatus.PENDING,
            target=TaskStatus.READY,
            sequence=1,
            occurred_at=occurred_at,
            trace_id=TraceId("0123456789abcdef0123456789abcdef"),
            reason_code="test",
        )


@pytest.mark.parametrize("reason", ["", "UPPER", "has space", "x" * 129])
def test_reason_code_is_bounded_canonical_data(reason: str) -> None:
    with pytest.raises(StateTransitionError, match="reason_code"):
        StateMachine().transition_run(
            run_id=RunId.new(),
            current=RunState.CREATED,
            target=RunState.PLANNING,
            sequence=1,
            occurred_at=datetime(2026, 8, 12, tzinfo=UTC),
            trace_id=TraceId("0123456789abcdef0123456789abcdef"),
            reason_code=reason,
        )
