import sqlite3
from datetime import timedelta

import pytest

from nexus_os.attempt_store import AttemptStore, AttemptStoreError
from nexus_os.domain import Failure, FailureClass, RunId, TaskId


def test_attempt_history_survives_restart_and_is_contiguous(tmp_path) -> None:
    path = tmp_path / "attempts.db"
    run_id = RunId.parse("83000000-0000-4000-8000-000000000001")
    task_id = TaskId("retry_task")
    first = AttemptStore(path)
    first.append(
        run_id,
        task_id,
        Failure(FailureClass.TIMEOUT, "tool.timeout", "Tool timed out.", True),
        cost=0.25,
        elapsed=timedelta(seconds=3),
    )
    first.close()
    reopened = AttemptStore(path)
    history = reopened.history(run_id, task_id)
    assert history[0].attempt == 1
    assert history[0].cost == 0.25
    assert history[0].elapsed == timedelta(seconds=3)


def test_attempt_rows_are_immutable_and_tampering_fails_integrity(tmp_path) -> None:
    store = AttemptStore(tmp_path / "attempts.db")
    run_id = RunId.parse("83000000-0000-4000-8000-000000000001")
    task_id = TaskId("retry_task")
    store.append(
        run_id,
        task_id,
        Failure(FailureClass.ENVIRONMENT, "tool.handler_failed", "Handler failed.", True),
        cost=0,
        elapsed=timedelta(),
    )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        store._connection.execute("UPDATE task_attempts SET attempt=2")
    store._connection.execute("DROP TRIGGER no_task_attempt_update")
    store._connection.execute("UPDATE task_attempts SET classification='UNKNOWN'")
    with pytest.raises(AttemptStoreError, match="integrity"):
        store.history(run_id, task_id)
