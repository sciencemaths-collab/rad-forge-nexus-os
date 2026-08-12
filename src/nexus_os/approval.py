"""Durable exact-scope, expiring, one-use human approval records."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from nexus_os.domain import ActionEffect, RunId

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ApprovalError(ValueError):
    """Safe approval validation, state, or scope failure."""


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    CONSUMED = "CONSUMED"


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    approval_id: UUID
    project_id: str
    run_id: RunId
    action_digest: str
    effect: ActionEffect
    requested_by: str
    requested_at: datetime
    expires_at: datetime
    status: ApprovalStatus
    decided_by: str | None = None
    decided_at: datetime | None = None
    reason: str | None = None


class ApprovalStore:
    """SQLite approval store whose authorization transition is atomic."""

    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS approvals (
            approval_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, run_id TEXT NOT NULL,
            action_digest TEXT NOT NULL, effect TEXT NOT NULL, requested_by TEXT NOT NULL,
            requested_at TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL,
            decided_by TEXT, decided_at TEXT, reason TEXT)"""
        )

    def close(self) -> None:
        self._connection.close()

    def request(
        self,
        *,
        approval_id: UUID,
        project_id: str,
        run_id: RunId,
        action_digest: str,
        effect: ActionEffect,
        requested_by: str,
        requested_at: datetime,
        expires_at: datetime,
    ) -> ApprovalRecord:
        if not isinstance(approval_id, UUID):
            raise ApprovalError("approval_id must be a UUID")
        _bounded(project_id, "project_id")
        _bounded(requested_by, "requested_by")
        if not isinstance(run_id, RunId):
            raise ApprovalError("run_id must be a RunId")
        if not isinstance(action_digest, str) or not _DIGEST.fullmatch(action_digest):
            raise ApprovalError("action_digest must be a sha256 digest")
        if effect not in {ActionEffect.SENSITIVE, ActionEffect.DESTRUCTIVE}:
            raise ApprovalError("approval effect must be sensitive or destructive")
        _utc(requested_at, "requested_at")
        _utc(expires_at, "expires_at")
        if expires_at <= requested_at:
            raise ApprovalError("expires_at must be after requested_at")
        try:
            self._connection.execute(
                "INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)",
                (
                    str(approval_id), project_id, str(run_id), action_digest, effect.value,
                    requested_by, requested_at.isoformat(), expires_at.isoformat(),
                    ApprovalStatus.PENDING.value,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ApprovalError("approval_id already exists") from exc
        return self.get(approval_id)

    def get(self, approval_id: UUID) -> ApprovalRecord:
        row = self._connection.execute(
            "SELECT * FROM approvals WHERE approval_id = ?", (str(approval_id),)
        ).fetchone()
        if row is None:
            raise ApprovalError("approval not found")
        return _record(row)

    def decide(
        self,
        approval_id: UUID,
        *,
        status: ApprovalStatus,
        decided_by: str,
        decided_at: datetime,
        reason: str | None = None,
    ) -> ApprovalRecord:
        if status not in {ApprovalStatus.APPROVED, ApprovalStatus.DENIED, ApprovalStatus.REVOKED}:
            raise ApprovalError("decision status must be approved, denied, or revoked")
        _bounded(decided_by, "decided_by")
        _utc(decided_at, "decided_at")
        if reason is not None and len(reason) > 2000:
            raise ApprovalError("reason exceeds 2000 characters")
        cursor = self._connection.execute(
            """UPDATE approvals SET status = ?, decided_by = ?, decided_at = ?, reason = ?
            WHERE approval_id = ? AND status = ?""",
            (status.value, decided_by, decided_at.isoformat(), reason,
             str(approval_id), ApprovalStatus.PENDING.value),
        )
        if cursor.rowcount != 1:
            raise ApprovalError("only pending approvals can be decided")
        return self.get(approval_id)

    def authorize_and_consume(
        self,
        approval_id: UUID,
        *,
        project_id: str,
        run_id: RunId,
        action_digest: str,
        now: datetime,
    ) -> ApprovalRecord:
        _utc(now, "now")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            record = self.get(approval_id)
            if record.status is not ApprovalStatus.APPROVED:
                raise ApprovalError("approval is not approved")
            if now >= record.expires_at:
                self._connection.execute(
                    "UPDATE approvals SET status = ? WHERE approval_id = ?",
                    (ApprovalStatus.EXPIRED.value, str(approval_id)),
                )
                self._connection.execute("COMMIT")
                raise ApprovalError("approval has expired")
            if (
                record.project_id != project_id
                or record.run_id != run_id
                or record.action_digest != action_digest
            ):
                raise ApprovalError("approval scope does not match action")
            cursor = self._connection.execute(
                "UPDATE approvals SET status = ? WHERE approval_id = ? AND status = ?",
                (ApprovalStatus.CONSUMED.value, str(approval_id), ApprovalStatus.APPROVED.value),
            )
            if cursor.rowcount != 1:
                raise ApprovalError("approval was already consumed")
            self._connection.execute("COMMIT")
            return self.get(approval_id)
        except Exception:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise


def _record(row: tuple[object, ...]) -> ApprovalRecord:
    return ApprovalRecord(
        UUID(str(row[0])), str(row[1]), RunId.parse(row[2]), str(row[3]),
        ActionEffect(str(row[4])), str(row[5]), datetime.fromisoformat(str(row[6])),
        datetime.fromisoformat(str(row[7])), ApprovalStatus(str(row[8])),
        None if row[9] is None else str(row[9]),
        None if row[10] is None else datetime.fromisoformat(str(row[10])),
        None if row[11] is None else str(row[11]),
    )


def _bounded(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ApprovalError(f"{name} must be a non-empty bounded string")


def _utc(value: datetime, name: str) -> None:
    invalid = (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    )
    if invalid:
        raise ApprovalError(f"{name} must be timezone-aware UTC")
