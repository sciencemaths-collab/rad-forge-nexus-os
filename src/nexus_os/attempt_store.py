"""Append-only durable task-attempt evidence for bounded retry decisions."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from pathlib import Path

from nexus_os.domain import Failure, FailureClass, RunId, TaskId
from nexus_os.retry import AttemptRecord


class AttemptStoreError(ValueError):
    """Safe attempt persistence or integrity failure."""


class AttemptStore:
    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript("""
        CREATE TABLE IF NOT EXISTS task_attempts (
          run_id TEXT NOT NULL, task_id TEXT NOT NULL, attempt INTEGER NOT NULL,
          classification TEXT NOT NULL, code TEXT NOT NULL, message TEXT NOT NULL,
          retryable INTEGER NOT NULL, details_json TEXT NOT NULL, cost REAL NOT NULL,
          elapsed_seconds REAL NOT NULL, PRIMARY KEY(run_id, task_id, attempt));
        CREATE TRIGGER IF NOT EXISTS no_task_attempt_update BEFORE UPDATE ON task_attempts
          BEGIN SELECT RAISE(ABORT, 'task attempts are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS no_task_attempt_delete BEFORE DELETE ON task_attempts
          BEGIN SELECT RAISE(ABORT, 'task attempts are append only'); END;
        """)

    def close(self) -> None:
        self._connection.close()

    def append(
        self,
        run_id: RunId,
        task_id: TaskId,
        failure: Failure,
        *,
        cost: float,
        elapsed: timedelta,
    ) -> AttemptRecord:
        history = self.history(run_id, task_id)
        record = AttemptRecord(len(history) + 1, failure, cost, elapsed)
        try:
            self._connection.execute(
                "INSERT INTO task_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(run_id),
                    str(task_id),
                    record.attempt,
                    failure.classification.value,
                    failure.code,
                    failure.message,
                    int(failure.retryable),
                    json.dumps(dict(failure.details), sort_keys=True, separators=(",", ":")),
                    cost,
                    elapsed.total_seconds(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise AttemptStoreError("task attempt sequence conflict") from exc
        return record

    def history(self, run_id: RunId, task_id: TaskId) -> tuple[AttemptRecord, ...]:
        rows = self._connection.execute(
            "SELECT * FROM task_attempts WHERE run_id=? AND task_id=? ORDER BY attempt",
            (str(run_id), str(task_id)),
        ).fetchall()
        try:
            records = tuple(
                AttemptRecord(
                    int(row[2]),
                    Failure(
                        FailureClass(str(row[3])),
                        str(row[4]),
                        str(row[5]),
                        bool(row[6]),
                        json.loads(str(row[7])),
                    ),
                    float(row[8]),
                    timedelta(seconds=float(row[9])),
                )
                for row in rows
            )
            if tuple(item.attempt for item in records) != tuple(range(1, len(records) + 1)):
                raise ValueError
            return records
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AttemptStoreError("stored task attempts failed integrity validation") from exc
