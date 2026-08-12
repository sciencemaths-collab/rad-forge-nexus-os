"""Transactional durable checkpoint storage behind provider-neutral values."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nexus_os.domain import RunId

MAX_CHECKPOINT_BYTES = 4 * 1024 * 1024
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SECRET_PREFIXES = ("env:", "vault:", "secret:")


class CheckpointError(ValueError):
    """Safe durable-store failure."""


class CheckpointConflictError(CheckpointError):
    """Optimistic revision mismatch."""


class CheckpointCompatibilityError(CheckpointError):
    """Checkpoint cannot resume under the requested graph/schema contract."""


@dataclass(frozen=True, slots=True)
class Checkpoint:
    run_id: RunId
    graph_digest: str
    schema_version: str
    revision: int
    payload: Mapping[str, Any]
    saved_at: datetime


class SQLiteCheckpointStore:
    """SQLite implementation with atomic compare-and-swap checkpoint writes."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        if self._path.exists() and not self._path.is_file():
            raise CheckpointError("checkpoint database path must be a regular file")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self._path, isolation_level=None)
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS checkpoints (
                run_id TEXT PRIMARY KEY,
                graph_digest TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision > 0),
                payload_json TEXT NOT NULL,
                saved_at TEXT NOT NULL
                )"""
            )
        except sqlite3.Error as exc:
            raise CheckpointError("unable to initialize checkpoint database") from exc

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> SQLiteCheckpointStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def save(
        self,
        *,
        run_id: RunId,
        graph_digest: str,
        schema_version: str,
        payload: Mapping[str, Any],
        expected_revision: int | None,
        saved_at: datetime,
    ) -> Checkpoint:
        _validate_metadata(graph_digest, schema_version, saved_at)
        payload_json = _canonical_payload(payload)
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT revision FROM checkpoints WHERE run_id = ?", (str(run_id),)
            ).fetchone()
            current = None if row is None else int(row[0])
            if current != expected_revision:
                raise CheckpointConflictError(
                    f"checkpoint revision conflict: expected {expected_revision}, found {current}"
                )
            revision = 1 if current is None else current + 1
            self._connection.execute(
                """INSERT INTO checkpoints
                (run_id, graph_digest, schema_version, revision, payload_json, saved_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                graph_digest=excluded.graph_digest,
                schema_version=excluded.schema_version,
                revision=excluded.revision,
                payload_json=excluded.payload_json,
                saved_at=excluded.saved_at""",
                (
                    str(run_id),
                    graph_digest,
                    schema_version,
                    revision,
                    payload_json,
                    saved_at.isoformat(),
                ),
            )
            self._connection.execute("COMMIT")
        except CheckpointConflictError:
            self._connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise CheckpointError("checkpoint write failed atomically") from exc
        return Checkpoint(
            run_id=run_id,
            graph_digest=graph_digest,
            schema_version=schema_version,
            revision=revision,
            payload=json.loads(payload_json),
            saved_at=saved_at,
        )

    def load(
        self,
        run_id: RunId,
        *,
        graph_digest: str | None = None,
        schema_version: str | None = None,
    ) -> Checkpoint | None:
        try:
            row = self._connection.execute(
                """SELECT graph_digest, schema_version, revision, payload_json, saved_at
                FROM checkpoints WHERE run_id = ?""",
                (str(run_id),),
            ).fetchone()
        except sqlite3.Error as exc:
            raise CheckpointError("checkpoint read failed") from exc
        if row is None:
            return None
        if graph_digest is not None and row[0] != graph_digest:
            raise CheckpointCompatibilityError("checkpoint graph digest does not match")
        if schema_version is not None and row[1] != schema_version:
            raise CheckpointCompatibilityError("checkpoint schema version does not match")
        try:
            return Checkpoint(
                run_id=run_id,
                graph_digest=str(row[0]),
                schema_version=str(row[1]),
                revision=int(row[2]),
                payload=json.loads(str(row[3])),
                saved_at=datetime.fromisoformat(str(row[4])),
            )
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise CheckpointError("stored checkpoint is corrupt") from exc


def _validate_metadata(graph_digest: str, schema_version: str, saved_at: datetime) -> None:
    if not _DIGEST.fullmatch(graph_digest):
        raise CheckpointError("graph_digest must be a SHA-256 digest")
    if schema_version != "1.0":
        raise CheckpointError("schema_version must be 1.0")
    if saved_at.tzinfo is None or saved_at.utcoffset() != UTC.utcoffset(saved_at):
        raise CheckpointError("saved_at must be timezone-aware UTC")


def _canonical_payload(payload: Mapping[str, Any]) -> str:
    if _contains_secret_reference(payload):
        raise CheckpointError("checkpoint payload must not contain secret references")
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CheckpointError("checkpoint payload must contain canonical JSON values") from exc
    if len(encoded.encode()) > MAX_CHECKPOINT_BYTES:
        raise CheckpointError("checkpoint payload exceeds the 4 MiB limit")
    return encoded


def _contains_secret_reference(value: object) -> bool:
    if isinstance(value, str):
        return value.startswith(_SECRET_PREFIXES)
    if isinstance(value, Mapping):
        return any(_contains_secret_reference(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_reference(item) for item in value)
    return False
