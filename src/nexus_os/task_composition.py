"""Durably bind qualified task reasoning to deterministic governed execution."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from nexus_os.domain import RunId, TaskDefinition, TaskId, TraceId
from nexus_os.task_reasoning import QualifiedTaskReasoner, ReasonedTaskArtifact

_RESERVED = frozenset({"reasoned_artifact", "reasoned_artifact_digest"})


class TaskCompositionError(ValueError):
    """Safe reasoning-binding, persistence, or integrity failure."""


class ReasonedTaskCompositionStore:
    """Persist one immutable qualified artifact for an exact approved task."""

    def __init__(self, path: Path, reasoner: QualifiedTaskReasoner) -> None:
        self._reasoner = reasoner
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript("""
        CREATE TABLE IF NOT EXISTS reasoned_task_compositions (
          run_id TEXT NOT NULL, task_id TEXT NOT NULL, task_digest TEXT NOT NULL,
          artifact_json TEXT NOT NULL, artifact_digest TEXT NOT NULL,
          PRIMARY KEY(run_id, task_id));
        CREATE TRIGGER IF NOT EXISTS no_reasoned_task_composition_update
          BEFORE UPDATE ON reasoned_task_compositions
          BEGIN SELECT RAISE(ABORT, 'reasoned task compositions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS no_reasoned_task_composition_delete
          BEFORE DELETE ON reasoned_task_compositions
          BEGIN SELECT RAISE(ABORT, 'reasoned task compositions are append only'); END;
        """)

    def close(self) -> None:
        self._connection.close()

    async def prepare(
        self,
        task: TaskDefinition,
        *,
        run_id: RunId,
        trace_id: TraceId,
        at: datetime,
    ) -> ReasonedTaskArtifact:
        """Ask the qualified reasoner and bind its complete proposal exactly once."""
        self._validate_input(task.input)
        artifact = await self._reasoner.propose(task, run_id=run_id, trace_id=trace_id, at=at)
        if artifact.unresolved_questions:
            raise TaskCompositionError("reasoned task has unresolved questions")
        values = (
            str(run_id),
            str(task.task_id),
            _task_digest(task),
            _canonical(artifact.to_dict()),
            artifact.digest,
        )
        try:
            self._connection.execute(
                "INSERT INTO reasoned_task_compositions VALUES (?, ?, ?, ?, ?)", values
            )
        except sqlite3.IntegrityError as exc:
            if self._row(run_id, task.task_id) != values:
                raise TaskCompositionError("reasoned task binding already exists") from exc
        return artifact

    def resolve(self, run_id: RunId, task: TaskDefinition) -> Mapping[str, Any]:
        """Return the approved input enriched only with its validated proposal."""
        self._validate_input(task.input)
        row = self._row(run_id, task.task_id)
        if row is None:
            raise TaskCompositionError("reasoned task binding is missing")
        if row[2] != _task_digest(task):
            raise TaskCompositionError("reasoned task binding does not match approved task")
        try:
            raw = json.loads(row[3])
            artifact = _artifact(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TaskCompositionError("stored reasoned task failed integrity validation") from exc
        if _canonical(raw) != row[3] or artifact.digest != row[4]:
            raise TaskCompositionError("stored reasoned task failed integrity validation")
        if artifact.unresolved_questions:
            raise TaskCompositionError("reasoned task has unresolved questions")
        return {
            **dict(task.input),
            "reasoned_artifact": artifact.to_dict(),
            "reasoned_artifact_digest": artifact.digest,
        }

    def _row(self, run_id: RunId, task_id: TaskId) -> tuple[str, str, str, str, str] | None:
        row = self._connection.execute(
            "SELECT run_id, task_id, task_digest, artifact_json, artifact_digest "
            "FROM reasoned_task_compositions WHERE run_id=? AND task_id=?",
            (str(run_id), str(task_id)),
        ).fetchone()
        if row is None:
            return None
        run, task, task_digest, artifact_json, artifact_digest = row
        return (str(run), str(task), str(task_digest), str(artifact_json), str(artifact_digest))

    @staticmethod
    def _validate_input(value: Mapping[str, Any]) -> None:
        if _RESERVED.intersection(value):
            raise TaskCompositionError("approved task input uses reserved reasoning fields")


def _task_digest(task: TaskDefinition) -> str:
    return "sha256:" + hashlib.sha256(_canonical(task.canonical_dict()).encode()).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _artifact(value: object) -> ReasonedTaskArtifact:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "title",
        "summary",
        "sections",
        "evidence_notes",
        "unresolved_questions",
    }:
        raise ValueError
    sections, evidence, questions = (
        value["sections"],
        value["evidence_notes"],
        value["unresolved_questions"],
    )
    if (
        not isinstance(sections, list)
        or not all(
            isinstance(item, dict) and set(item) == {"heading", "content"} for item in sections
        )
        or not isinstance(evidence, list)
        or not isinstance(questions, list)
    ):
        raise ValueError
    return ReasonedTaskArtifact(
        value["title"],
        value["summary"],
        tuple((item["heading"], item["content"]) for item in sections),
        tuple(evidence),
        tuple(questions),
        value["schema_version"],
    )
