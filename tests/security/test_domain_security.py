"""Security and failure tests for domain boundary validation."""

import math

import pytest

from nexus_os.domain import ActionEffect, DomainValidationError, TaskDefinition, TaskId


@pytest.mark.parametrize(
    "payload",
    [
        {"secret": object()},
        {"not_finite": math.nan},
        {"positive_infinity": math.inf},
        {1: "non-string key"},
    ],
)
def test_task_input_rejects_non_json_or_non_canonical_values(payload: object) -> None:
    with pytest.raises(DomainValidationError, match="input"):
        TaskDefinition(
            task_id=TaskId("task_ok"),
            kind="test",
            depends_on=(),
            effect=ActionEffect.READ_ONLY,
            timeout_seconds=1,
            max_attempts=1,
            backoff_seconds=0,
            input=payload,  # type: ignore[arg-type]
        )
