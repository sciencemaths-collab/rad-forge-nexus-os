"""Security and failure tests for durable checkpoints."""

from datetime import UTC, datetime

import pytest

from nexus_os.domain import RunId
from nexus_os.stores import MAX_CHECKPOINT_BYTES, CheckpointError, SQLiteCheckpointStore


def _save(store: SQLiteCheckpointStore, payload: dict[str, object]) -> None:
    store.save(
        run_id=RunId.new(),
        graph_digest="sha256:" + "a" * 64,
        schema_version="1.0",
        payload=payload,
        expected_revision=None,
        saved_at=datetime(2026, 8, 12, tzinfo=UTC),
    )


def test_secret_references_and_noncanonical_values_are_not_persisted(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with SQLiteCheckpointStore(tmp_path / "state.db") as store:
        with pytest.raises(CheckpointError, match="secret references"):
            _save(store, {"credential": "env:OPENAI_API_KEY"})
        with pytest.raises(CheckpointError, match="canonical JSON"):
            _save(store, {"value": float("nan")})


def test_oversized_checkpoint_is_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with SQLiteCheckpointStore(tmp_path / "state.db") as store:
        with pytest.raises(CheckpointError, match="4 MiB"):
            _save(store, {"padding": "x" * (MAX_CHECKPOINT_BYTES + 1)})
