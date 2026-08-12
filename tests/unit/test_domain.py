"""Contract tests for provider-neutral core domain values."""

from datetime import UTC, datetime
from types import MappingProxyType
from uuid import UUID, uuid4

import pytest

from nexus_os.domain import (
    ActionEffect,
    ArtifactRef,
    DomainValidationError,
    Failure,
    FailureClass,
    RunId,
    RunState,
    RuntimeCommand,
    RuntimeCommandKind,
    TaskDefinition,
    TaskEvent,
    TaskEventKind,
    TaskGraph,
    TaskId,
    TaskResult,
    TaskStatus,
    TraceId,
)


def test_uuid_identifier_generation_and_parsing_are_typed() -> None:
    generated = RunId.new()
    reparsed = RunId.parse(str(generated))

    assert reparsed == generated
    assert isinstance(generated.value, UUID)
    assert RunId.parse(uuid4()) != generated


@pytest.mark.parametrize("value", ["", "not-a-uuid", 42, None])
def test_uuid_identifier_rejects_invalid_values(value: object) -> None:
    with pytest.raises(DomainValidationError, match="run_id"):
        RunId.parse(value)


@pytest.mark.parametrize("value", ["a", "Uppercase", "1-start", "bad space", "a" * 65])
def test_task_identifier_rejects_values_outside_contract(value: str) -> None:
    with pytest.raises(DomainValidationError, match="task_id"):
        TaskId(value)


def test_task_definition_copies_and_freezes_untrusted_input() -> None:
    payload: dict[str, object] = {"query": {"limit": 10}, "columns": ["a", "b"]}
    task = TaskDefinition(
        task_id=TaskId("load_data"),
        kind="deterministic.csv.import",
        depends_on=(),
        effect=ActionEffect.WORKSPACE_WRITE,
        timeout_seconds=30,
        max_attempts=2,
        backoff_seconds=0.5,
        input=payload,
        acceptance_ids=("RW-100K-01",),
    )
    payload["query"] = "changed"

    assert isinstance(task.input, MappingProxyType)
    assert task.input["query"]["limit"] == 10
    assert task.input["columns"] == ("a", "b")
    with pytest.raises(TypeError):
        task.input["new"] = True  # type: ignore[index]


@pytest.mark.parametrize(
    ("field", "value"),
    [("timeout_seconds", 0), ("max_attempts", 0), ("max_attempts", 21), ("backoff_seconds", -1)],
)
def test_task_definition_enforces_resource_bounds(field: str, value: int) -> None:
    values: dict[str, object] = {
        "task_id": TaskId("task_ok"),
        "kind": "test",
        "depends_on": (),
        "effect": ActionEffect.READ_ONLY,
        "timeout_seconds": 1,
        "max_attempts": 1,
        "backoff_seconds": 0,
        "input": {},
    }
    values[field] = value
    with pytest.raises(DomainValidationError, match=field):
        TaskDefinition(**values)  # type: ignore[arg-type]


def test_task_graph_rejects_duplicate_ids_but_defers_graph_semantics() -> None:
    first = _task("first", depends_on=(TaskId("second"),))
    second = _task("second", depends_on=(TaskId("first"),))

    graph = TaskGraph(graph_id=uuid4(), project_id="project", tasks=(first, second))
    assert len(graph.tasks) == 2
    with pytest.raises(DomainValidationError, match="duplicate task_id"):
        TaskGraph(graph_id=uuid4(), project_id="project", tasks=(_task("first"), _task("first")))


def test_task_graph_has_stable_canonical_digest_independent_of_input_order() -> None:
    graph_id = uuid4()
    first = _task("first")
    second = _task("second", depends_on=(first.task_id,))

    left = TaskGraph(graph_id=graph_id, project_id="project", tasks=(first, second))
    right = TaskGraph(graph_id=graph_id, project_id="project", tasks=(second, first))

    assert left.digest == right.digest
    assert left.canonical_dict() == right.canonical_dict()


def test_failure_taxonomy_and_retry_hint_are_validated() -> None:
    failure = Failure(
        classification=FailureClass.PROVIDER,
        code="provider_unavailable",
        message="Provider unavailable",
        retryable=True,
        details={"status": 503},
    )

    assert failure.details["status"] == 503
    with pytest.raises(DomainValidationError, match="must not be retryable"):
        Failure(
            classification=FailureClass.SECURITY_POLICY,
            code="blocked",
            message="Denied",
            retryable=True,
        )


def test_task_result_requires_failure_only_for_failed_status() -> None:
    failure = Failure(
        classification=FailureClass.PROVIDER,
        code="provider_error",
        message="Provider failed",
        retryable=True,
    )
    with pytest.raises(DomainValidationError, match="requires a failure"):
        TaskResult(task_id=TaskId("task_ok"), status=TaskStatus.FAILED)
    with pytest.raises(DomainValidationError, match="cannot carry a failure"):
        TaskResult(task_id=TaskId("task_ok"), status=TaskStatus.SUCCEEDED, failure=failure)


def test_event_requires_utc_time_positive_sequence_and_valid_trace() -> None:
    event = TaskEvent(
        task_id=TaskId("task_ok"),
        sequence=1,
        occurred_at=datetime(2026, 8, 12, tzinfo=UTC),
        kind=TaskEventKind.STARTED,
        trace_id=TraceId("0123456789abcdef0123456789abcdef"),
        payload={"provider": "mock"},
    )

    assert event.payload["provider"] == "mock"
    with pytest.raises(DomainValidationError, match="timezone-aware UTC"):
        TaskEvent(
            task_id=TaskId("task_ok"),
            sequence=1,
            occurred_at=datetime(2026, 8, 12),
            kind=TaskEventKind.STARTED,
            trace_id=TraceId("0123456789abcdef0123456789abcdef"),
        )


def test_runtime_command_is_immutable_and_requires_idempotency_key() -> None:
    command = RuntimeCommand(
        command_id=uuid4(),
        run_id=RunId.new(),
        kind=RuntimeCommandKind.CANCEL_RUN,
        issued_at=datetime(2026, 8, 12, tzinfo=UTC),
        trace_id=TraceId("0123456789abcdef0123456789abcdef"),
        idempotency_key="cancel-request-1",
        payload={"reason": "operator request"},
    )

    assert command.payload["reason"] == "operator request"
    with pytest.raises(DomainValidationError, match="idempotency_key"):
        RuntimeCommand(
            command_id=uuid4(),
            run_id=RunId.new(),
            kind=RuntimeCommandKind.START_RUN,
            issued_at=datetime(2026, 8, 12, tzinfo=UTC),
            trace_id=TraceId("0123456789abcdef0123456789abcdef"),
            idempotency_key="",
        )


def test_artifact_reference_rejects_paths_and_unverified_digests() -> None:
    artifact = ArtifactRef(
        artifact_id="summary",
        uri="artifact://runs/run-1/summary.json",
        digest="sha256:" + "a" * 64,
        media_type="application/json",
        size_bytes=42,
    )
    assert artifact.size_bytes == 42

    with pytest.raises(DomainValidationError, match="artifact URI"):
        ArtifactRef(
            artifact_id="bad",
            uri="../../secret",
            digest="sha256:" + "a" * 64,
            media_type="text/plain",
            size_bytes=1,
        )


def test_lifecycle_enums_are_explicit_and_terminal_states_are_identifiable() -> None:
    assert RunState.SUCCEEDED.is_terminal
    assert RunState.CANCELLED.is_terminal
    assert not RunState.RUNNING.is_terminal
    assert TaskStatus.BLOCKED.value == "BLOCKED"


def _task(name: str, *, depends_on: tuple[TaskId, ...] = ()) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(name),
        kind="test",
        depends_on=depends_on,
        effect=ActionEffect.READ_ONLY,
        timeout_seconds=1,
        max_attempts=1,
        backoff_seconds=0,
        input={},
    )
