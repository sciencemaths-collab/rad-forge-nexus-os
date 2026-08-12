"""Unit contracts for bounded retry and repair decisions."""

from datetime import timedelta

import pytest

from nexus_os.domain import Failure, FailureClass
from nexus_os.retry import (
    AttemptRecord,
    RetryAction,
    RetryEngine,
    RetryLimits,
    RetryValidationError,
)


def _failure(kind: FailureClass = FailureClass.PROVIDER, *, retryable: bool = True) -> Failure:
    return Failure(kind, "provider.busy", "provider unavailable", retryable)


def test_retry_is_allowed_with_deterministic_capped_backoff() -> None:
    engine = RetryEngine(RetryLimits(4, timedelta(minutes=5), 10.0, 3, 30.0))
    decision = engine.decide(
        history=(AttemptRecord(1, _failure(), 1.0, timedelta(seconds=2)),),
        next_estimated_cost=2.0,
    )
    assert decision.action is RetryAction.RETRY
    assert decision.next_attempt == 2
    assert decision.delay_seconds == 2.0


def test_implementation_failure_routes_to_bounded_repair() -> None:
    decision = RetryEngine(RetryLimits()).decide(
        history=(AttemptRecord(1, _failure(FailureClass.IMPLEMENTATION_BUG), 0, timedelta()),),
        next_estimated_cost=0,
    )
    assert decision.action is RetryAction.REPAIR


@pytest.mark.parametrize(
    ("history", "cost", "reason"),
    [
        (
            tuple(AttemptRecord(number, _failure(), 0, timedelta()) for number in range(1, 4)),
            0,
            "attempt limit",
        ),
        ((AttemptRecord(1, _failure(), 0, timedelta(minutes=10)),), 0, "elapsed limit"),
        ((AttemptRecord(1, _failure(), 9, timedelta()),), 2, "budget limit"),
        (
            tuple(AttemptRecord(number, _failure(), 0, timedelta()) for number in range(1, 3)),
            0,
            "repeated failure",
        ),
    ],
)
def test_bounds_stop_execution(history, cost, reason) -> None:  # type: ignore[no-untyped-def]
    limits = RetryLimits(3, timedelta(minutes=5), 10.0, 2, 60.0)
    decision = RetryEngine(limits).decide(history=history, next_estimated_cost=cost)
    assert decision.action is RetryAction.STOP
    assert reason in decision.reason


def test_nonretryable_and_security_failures_stop() -> None:
    engine = RetryEngine(RetryLimits())
    for failure in (
        _failure(retryable=False),
        Failure(FailureClass.SECURITY_POLICY, "policy.denied", "denied", False),
    ):
        decision = engine.decide(
            history=(AttemptRecord(1, failure, 0, timedelta()),), next_estimated_cost=0
        )
        assert decision.action is RetryAction.STOP


def test_invalid_limits_and_noncontiguous_history_are_rejected() -> None:
    with pytest.raises(RetryValidationError):
        RetryLimits(max_attempts=0)
    engine = RetryEngine(RetryLimits())
    history = (AttemptRecord(2, _failure(), 0, timedelta()),)
    with pytest.raises(RetryValidationError, match="contiguous"):
        engine.decide(history=history, next_estimated_cost=0)
