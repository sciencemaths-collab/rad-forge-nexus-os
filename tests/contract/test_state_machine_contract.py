"""Contract tests for deterministic NEXUS lifecycle transitions."""

from datetime import UTC, datetime

import pytest

from nexus_os.domain import Failure, FailureClass, RunId, RunState, TaskId, TaskStatus, TraceId
from nexus_os.state_machine import StateMachine, StateTransitionError

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
TRACE = TraceId("0123456789abcdef0123456789abcdef")


def test_run_happy_path_is_explicit_and_deterministic() -> None:
    machine = StateMachine()
    run_id = RunId.parse("12345678-1234-5678-1234-567812345678")

    planning = machine.transition_run(
        run_id=run_id,
        current=RunState.CREATED,
        target=RunState.PLANNING,
        sequence=1,
        occurred_at=NOW,
        trace_id=TRACE,
        reason_code="plan_requested",
    )
    ready = machine.transition_run(
        run_id=run_id,
        current=planning.target,
        target=RunState.READY,
        sequence=2,
        occurred_at=NOW,
        trace_id=TRACE,
        reason_code="plan_validated",
    )

    assert planning.source is RunState.CREATED
    assert ready.source is RunState.PLANNING
    assert ready.sequence == 2


def test_illegal_and_terminal_run_transitions_fail_closed() -> None:
    machine = StateMachine()
    values = _run_values()

    with pytest.raises(StateTransitionError, match="illegal run transition"):
        machine.transition_run(current=RunState.CREATED, target=RunState.RUNNING, **values)
    with pytest.raises(StateTransitionError, match="terminal run state"):
        machine.transition_run(current=RunState.SUCCEEDED, target=RunState.FAILED, **values)


def test_cancellation_requires_durable_cancelling_state() -> None:
    machine = StateMachine()
    values = _run_values()

    with pytest.raises(StateTransitionError, match="illegal run transition"):
        machine.transition_run(current=RunState.RUNNING, target=RunState.CANCELLED, **values)
    record = machine.transition_run(
        current=RunState.CANCELLING,
        target=RunState.CANCELLED,
        **values,
    )
    assert record.target is RunState.CANCELLED


def test_failed_task_requires_structured_failure() -> None:
    machine = StateMachine()
    values = _task_values()

    with pytest.raises(StateTransitionError, match="requires failure"):
        machine.transition_task(current=TaskStatus.RUNNING, target=TaskStatus.FAILED, **values)

    failure = Failure(
        classification=FailureClass.PROVIDER,
        code="provider_error",
        message="Provider failed",
        retryable=True,
    )
    record = machine.transition_task(
        current=TaskStatus.RUNNING,
        target=TaskStatus.FAILED,
        failure=failure,
        **values,
    )
    assert record.failure == failure


def test_nonfailed_task_transition_rejects_failure() -> None:
    failure = Failure(
        classification=FailureClass.ENVIRONMENT,
        code="disk_full",
        message="Disk full",
        retryable=True,
    )
    with pytest.raises(StateTransitionError, match="only FAILED"):
        StateMachine().transition_task(
            current=TaskStatus.RUNNING,
            target=TaskStatus.SUCCEEDED,
            failure=failure,
            **_task_values(),
        )


def test_task_terminal_state_cannot_be_reopened_for_retry() -> None:
    with pytest.raises(StateTransitionError, match="terminal task state"):
        StateMachine().transition_task(
            current=TaskStatus.FAILED,
            target=TaskStatus.READY,
            **_task_values(),
        )


def test_transition_predicates_cover_every_state_pair_without_raising() -> None:
    machine = StateMachine()

    run_answers = {
        (source, target): machine.can_transition_run(source, target)
        for source in RunState
        for target in RunState
    }
    task_answers = {
        (source, target): machine.can_transition_task(source, target)
        for source in TaskStatus
        for target in TaskStatus
    }

    assert len(run_answers) == len(RunState) ** 2
    assert len(task_answers) == len(TaskStatus) ** 2
    assert not any(
        allowed for (source, _), allowed in run_answers.items() if source.is_terminal
    )
    assert not any(
        allowed for (source, _), allowed in task_answers.items() if source.is_terminal
    )


def _run_values() -> dict[str, object]:
    return {
        "run_id": RunId.parse("12345678-1234-5678-1234-567812345678"),
        "sequence": 1,
        "occurred_at": NOW,
        "trace_id": TRACE,
        "reason_code": "contract_test",
    }


def _task_values() -> dict[str, object]:
    return {
        "run_id": RunId.parse("12345678-1234-5678-1234-567812345678"),
        "task_id": TaskId("task_one"),
        "sequence": 1,
        "occurred_at": NOW,
        "trace_id": TRACE,
        "reason_code": "contract_test",
    }
