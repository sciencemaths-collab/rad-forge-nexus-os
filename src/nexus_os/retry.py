"""Deterministic bounded retry and repair decisions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from nexus_os.domain import Failure, FailureClass


class RetryValidationError(ValueError):
    """Safe rejection of invalid retry limits or attempt history."""


class RetryAction(StrEnum):
    RETRY = "RETRY"
    REPAIR = "REPAIR"
    STOP = "STOP"


@dataclass(frozen=True, slots=True)
class RetryLimits:
    max_attempts: int = 3
    max_elapsed: timedelta = timedelta(minutes=15)
    max_cost: float = 25.0
    max_repeated_failures: int = 2
    max_backoff_seconds: float = 300.0

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or not 1 <= self.max_attempts <= 20:
            raise RetryValidationError("max_attempts must be from 1 to 20")
        if not timedelta() < self.max_elapsed <= timedelta(days=7):
            raise RetryValidationError("max_elapsed must be positive and at most 7 days")
        _finite_nonnegative(self.max_cost, "max_cost")
        invalid_repeated_limit = (
            not isinstance(self.max_repeated_failures, int)
            or not 1 <= self.max_repeated_failures <= 20
        )
        if invalid_repeated_limit:
            raise RetryValidationError("max_repeated_failures must be from 1 to 20")
        _finite_nonnegative(self.max_backoff_seconds, "max_backoff_seconds")


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    attempt: int
    failure: Failure
    cost: float
    elapsed: timedelta

    def __post_init__(self) -> None:
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise RetryValidationError("attempt must be positive")
        _finite_nonnegative(self.cost, "attempt cost")
        if self.elapsed < timedelta():
            raise RetryValidationError("attempt elapsed time must not be negative")


@dataclass(frozen=True, slots=True)
class RetryDecision:
    action: RetryAction
    reason: str
    next_attempt: int | None = None
    delay_seconds: float = 0.0


class RetryEngine:
    """Apply every configured bound before permitting another attempt."""

    def __init__(self, limits: RetryLimits) -> None:
        self._limits = limits

    def decide(
        self,
        *,
        history: tuple[AttemptRecord, ...],
        next_estimated_cost: float,
    ) -> RetryDecision:
        _finite_nonnegative(next_estimated_cost, "next estimated cost")
        if not history:
            raise RetryValidationError("attempt history must not be empty")
        if tuple(item.attempt for item in history) != tuple(range(1, len(history) + 1)):
            raise RetryValidationError("attempt history must be contiguous and ordered")
        latest = history[-1]
        if not latest.failure.retryable:
            return RetryDecision(RetryAction.STOP, "failure is not retryable")
        if len(history) >= self._limits.max_attempts:
            return RetryDecision(RetryAction.STOP, "attempt limit reached")
        if sum((item.elapsed for item in history), timedelta()) >= self._limits.max_elapsed:
            return RetryDecision(RetryAction.STOP, "elapsed limit reached")
        if sum(item.cost for item in history) + next_estimated_cost > self._limits.max_cost:
            return RetryDecision(RetryAction.STOP, "budget limit reached")
        fingerprint = (latest.failure.classification, latest.failure.code)
        repeated = sum(
            (item.failure.classification, item.failure.code) == fingerprint for item in history
        )
        if repeated >= self._limits.max_repeated_failures:
            return RetryDecision(RetryAction.STOP, "repeated failure limit reached")

        repairable = {
            FailureClass.IMPLEMENTATION_BUG,
            FailureClass.CONTRACT_MISMATCH,
            FailureClass.MISSING_DEPENDENCY,
        }
        action = (
            RetryAction.REPAIR if latest.failure.classification in repairable else RetryAction.RETRY
        )
        delay = min(2 ** (len(history) - 1) * 2.0, self._limits.max_backoff_seconds)
        return RetryDecision(action, "bounded next attempt permitted", len(history) + 1, delay)


def _finite_nonnegative(value: float, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise RetryValidationError(f"{name} must be finite and non-negative")
