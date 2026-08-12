"""Integration tests for SQLite checkpoint durability and resume."""

from datetime import UTC, datetime
from multiprocessing import Event, get_context
from pathlib import Path
from typing import Any

import pytest

from nexus_os.domain import RunId
from nexus_os.stores import (
    CheckpointCompatibilityError,
    CheckpointConflictError,
    SQLiteCheckpointStore,
)

DIGEST = "sha256:" + "a" * 64
NOW = datetime(2026, 8, 12, 12, tzinfo=UTC)


def test_checkpoint_save_update_close_reopen_and_resume(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "state.db"
    run_id = RunId.new()
    with SQLiteCheckpointStore(path) as store:
        first = store.save(
            run_id=run_id,
            graph_digest=DIGEST,
            schema_version="1.0",
            payload={"state": "RUNNING", "last_event": 3},
            expected_revision=None,
            saved_at=NOW,
        )
        second = store.save(
            run_id=run_id,
            graph_digest=DIGEST,
            schema_version="1.0",
            payload={"state": "PAUSED", "last_event": 4},
            expected_revision=first.revision,
            saved_at=NOW,
        )
        assert second.revision == 2

    with SQLiteCheckpointStore(path) as reopened:
        loaded = reopened.load(run_id, graph_digest=DIGEST, schema_version="1.0")
        assert loaded is not None
        assert loaded.revision == 2
        assert loaded.payload["state"] == "PAUSED"


def test_stale_writer_is_rejected_without_overwrite(tmp_path) -> None:  # type: ignore[no-untyped-def]
    run_id = RunId.new()
    with SQLiteCheckpointStore(tmp_path / "state.db") as store:
        store.save(
            run_id=run_id,
            graph_digest=DIGEST,
            schema_version="1.0",
            payload={"value": 1},
            expected_revision=None,
            saved_at=NOW,
        )
        with pytest.raises(CheckpointConflictError, match="expected None, found 1"):
            store.save(
                run_id=run_id,
                graph_digest=DIGEST,
                schema_version="1.0",
                payload={"value": 2},
                expected_revision=None,
                saved_at=NOW,
            )
        assert store.load(run_id).payload["value"] == 1  # type: ignore[union-attr]


def test_resume_rejects_incompatible_graph_or_schema(tmp_path) -> None:  # type: ignore[no-untyped-def]
    run_id = RunId.new()
    with SQLiteCheckpointStore(tmp_path / "state.db") as store:
        store.save(
            run_id=run_id,
            graph_digest=DIGEST,
            schema_version="1.0",
            payload={},
            expected_revision=None,
            saved_at=NOW,
        )
        with pytest.raises(CheckpointCompatibilityError, match="graph digest"):
            store.load(run_id, graph_digest="sha256:" + "b" * 64)
        with pytest.raises(CheckpointCompatibilityError, match="schema version"):
            store.load(run_id, schema_version="2.0")


def test_committed_checkpoint_survives_writer_process_kill(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "crash.db"
    run_id = RunId.new()
    context = get_context("spawn")
    committed = context.Event()
    process = context.Process(target=_write_and_wait, args=(path, str(run_id), committed))
    process.start()
    assert committed.wait(timeout=10)
    process.terminate()
    process.join(timeout=10)
    assert not process.is_alive()

    with SQLiteCheckpointStore(path) as store:
        recovered = store.load(run_id, graph_digest=DIGEST, schema_version="1.0")
        assert recovered is not None
        assert recovered.payload == {"state": "RUNNING"}


def _write_and_wait(path: Path, run_id: str, committed: Any) -> None:
    with SQLiteCheckpointStore(path) as store:
        store.save(
            run_id=RunId.parse(run_id),
            graph_digest=DIGEST,
            schema_version="1.0",
            payload={"state": "RUNNING"},
            expected_revision=None,
            saved_at=NOW,
        )
        committed.set()
        Event().wait()
