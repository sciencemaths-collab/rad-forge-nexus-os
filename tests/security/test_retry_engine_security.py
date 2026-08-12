"""Security/failure tests for bounded repair."""

from datetime import timedelta

import pytest

from nexus_os.domain import Failure, FailureClass
from nexus_os.retry import AttemptRecord, RetryEngine, RetryLimits, RetryValidationError


def test_negative_nan_and_infinite_costs_are_rejected() -> None:
    engine = RetryEngine(RetryLimits())
    failure = Failure(FailureClass.PROVIDER, "provider.fail", "failed", True)
    for value in (-1.0, float("nan"), float("inf")):
        with pytest.raises(RetryValidationError, match="cost"):
            engine.decide(
                history=(AttemptRecord(1, failure, 0, timedelta()),),
                next_estimated_cost=value,
            )


def test_cancellation_is_never_retried() -> None:
    failure = Failure(FailureClass.CANCELLED, "run.cancelled", "cancelled", False)
    decision = RetryEngine(RetryLimits()).decide(
        history=(AttemptRecord(1, failure, 0, timedelta()),), next_estimated_cost=0
    )
    assert decision.reason == "failure is not retryable"
