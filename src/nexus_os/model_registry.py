"""Durable, revocable registry for independently attested model qualifications."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from nexus_os.model_qualification import (
    EvaluationCategory,
    EvaluationResult,
    ModelEvaluation,
    ModelQualification,
    ModelUse,
    qualify_model,
)
from nexus_os.secrets import redact

_ACTOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
_ATTESTATION_FIELDS = {
    "schema_version",
    "manifest_digest",
    "evidence_count",
    "evidence_head",
    "attested_at",
    "attestor_producers",
    "qualification",
    "attestation_digest",
}


class ModelRegistryError(ValueError):
    """Safe registry validation, state, integrity, or authorization failure."""


class RegistryStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class RegistryRecord:
    attestation: dict[str, Any]
    qualification: ModelQualification
    registered_at: datetime
    registered_by: str
    status: RegistryStatus
    status_at: datetime | None = None
    status_by: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": "1.0",
            "attestation": self.attestation,
            "registered_at": _timestamp(self.registered_at),
            "registered_by": self.registered_by,
            "status": self.status.value,
        }
        if self.status_at is not None:
            value["status_at"] = _timestamp(self.status_at)
        if self.status_by is not None:
            value["status_by"] = self.status_by
        if self.reason is not None:
            value["reason"] = self.reason
        return value


class ModelQualificationRegistry:
    """SQLite registry with atomic replacement and irreversible revocation."""

    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS model_qualifications (
              qualification_id TEXT PRIMARY KEY,
              provider_id TEXT NOT NULL,
              model_id TEXT NOT NULL,
              adapter_version TEXT NOT NULL,
              attestation_digest TEXT NOT NULL UNIQUE,
              attestation_json TEXT NOT NULL,
              registered_at TEXT NOT NULL,
              registered_by TEXT NOT NULL,
              status TEXT NOT NULL,
              status_at TEXT,
              status_by TEXT,
              reason TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_model_qualification
              ON model_qualifications(provider_id, model_id, adapter_version)
              WHERE status = 'ACTIVE';
            CREATE TRIGGER IF NOT EXISTS no_model_qualification_delete
              BEFORE DELETE ON model_qualifications BEGIN
                SELECT RAISE(ABORT, 'model qualification records are append preserving');
              END;
            CREATE TRIGGER IF NOT EXISTS immutable_model_qualification_content
              BEFORE UPDATE ON model_qualifications
              WHEN NEW.qualification_id != OLD.qualification_id
                OR NEW.provider_id != OLD.provider_id OR NEW.model_id != OLD.model_id
                OR NEW.adapter_version != OLD.adapter_version
                OR NEW.attestation_digest != OLD.attestation_digest
                OR NEW.attestation_json != OLD.attestation_json
                OR NEW.registered_at != OLD.registered_at
                OR NEW.registered_by != OLD.registered_by
              BEGIN SELECT RAISE(ABORT, 'model qualification content is immutable'); END;
            """
        )

    def close(self) -> None:
        self._connection.close()

    def register(
        self,
        attestation: dict[str, Any],
        *,
        registered_at: datetime,
        registered_by: str,
    ) -> RegistryRecord:
        document, qualification, attested_at = _verify_attestation(attestation)
        _utc(registered_at, "registered_at")
        _actor(registered_by, "registered_by")
        if registered_at < attested_at or registered_at >= qualification.expires_at:
            raise ModelRegistryError("qualification is not current at registration time")
        encoded = _canonical(document).decode()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._connection.execute(
                """UPDATE model_qualifications
                   SET status = ?, status_at = ?, status_by = ?, reason = ?
                   WHERE provider_id = ? AND model_id = ? AND adapter_version = ?
                     AND status = ?""",
                (
                    RegistryStatus.SUPERSEDED.value,
                    registered_at.isoformat(),
                    registered_by,
                    "replaced by a newer independently attested qualification",
                    qualification.provider_id,
                    qualification.model_id,
                    qualification.adapter_version,
                    RegistryStatus.ACTIVE.value,
                ),
            )
            self._connection.execute(
                """INSERT INTO model_qualifications
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)""",
                (
                    str(qualification.qualification_id),
                    qualification.provider_id,
                    qualification.model_id,
                    qualification.adapter_version,
                    document["attestation_digest"],
                    encoded,
                    registered_at.isoformat(),
                    registered_by,
                    RegistryStatus.ACTIVE.value,
                ),
            )
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise ModelRegistryError("qualification or attestation already exists") from exc
        except Exception:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise
        return self.get(qualification.qualification_id)

    def get(self, qualification_id: UUID) -> RegistryRecord:
        if not isinstance(qualification_id, UUID):
            raise ModelRegistryError("qualification_id must be a UUID")
        row = self._connection.execute(
            "SELECT * FROM model_qualifications WHERE qualification_id = ?",
            (str(qualification_id),),
        ).fetchone()
        if row is None:
            raise ModelRegistryError("qualification not found")
        return _record(row)

    def revoke(
        self,
        qualification_id: UUID,
        *,
        revoked_at: datetime,
        revoked_by: str,
        reason: str,
    ) -> RegistryRecord:
        _utc(revoked_at, "revoked_at")
        _actor(revoked_by, "revoked_by")
        _reason(reason)
        current = self.get(qualification_id)
        if revoked_at < current.registered_at:
            raise ModelRegistryError("revocation predates registration")
        cursor = self._connection.execute(
            """UPDATE model_qualifications
               SET status = ?, status_at = ?, status_by = ?, reason = ?
               WHERE qualification_id = ? AND status = ?""",
            (
                RegistryStatus.REVOKED.value,
                revoked_at.isoformat(),
                revoked_by,
                reason,
                str(qualification_id),
                RegistryStatus.ACTIVE.value,
            ),
        )
        if cursor.rowcount != 1:
            raise ModelRegistryError("only an active qualification can be revoked")
        return self.get(qualification_id)

    def authorize(
        self,
        *,
        provider_id: str,
        model_id: str,
        adapter_version: str,
        use: ModelUse,
        at: datetime,
    ) -> RegistryRecord:
        _utc(at, "at")
        if not isinstance(use, ModelUse):
            raise ModelRegistryError("use must be a ModelUse")
        rows = self._connection.execute(
            """SELECT * FROM model_qualifications
               WHERE provider_id = ? AND model_id = ? AND adapter_version = ?
                 AND status = ?""",
            (provider_id, model_id, adapter_version, RegistryStatus.ACTIVE.value),
        ).fetchall()
        if len(rows) != 1:
            raise ModelRegistryError("no unique active qualification for exact model binding")
        record = _record(rows[0])
        if not record.qualification.permits(use, at=at):
            raise ModelRegistryError("qualification does not permit requested model use")
        return record

    def active(self, *, at: datetime) -> tuple[RegistryRecord, ...]:
        """Return integrity-verified, unexpired active records in canonical order."""
        _utc(at, "at")
        rows = self._connection.execute(
            """SELECT * FROM model_qualifications WHERE status = ?
               ORDER BY provider_id, model_id, adapter_version""",
            (RegistryStatus.ACTIVE.value,),
        ).fetchall()
        records = tuple(_record(row) for row in rows)
        return tuple(item for item in records if at < item.qualification.expires_at)


def _record(row: tuple[object, ...]) -> RegistryRecord:
    try:
        document = json.loads(str(row[5]))
        if not isinstance(document, dict):
            raise ValueError
        attestation, qualification, _ = _verify_attestation(document)
        if (
            str(qualification.qualification_id) != str(row[0])
            or qualification.provider_id != str(row[1])
            or qualification.model_id != str(row[2])
            or qualification.adapter_version != str(row[3])
            or attestation["attestation_digest"] != str(row[4])
        ):
            raise ValueError
        registered_at = datetime.fromisoformat(str(row[6]))
        _utc(registered_at, "stored registered_at")
        registered_by = str(row[7])
        _actor(registered_by, "stored registered_by")
        status = RegistryStatus(str(row[8]))
        status_at = None if row[9] is None else datetime.fromisoformat(str(row[9]))
        status_by = None if row[10] is None else str(row[10])
        reason = None if row[11] is None else str(row[11])
        if status is RegistryStatus.ACTIVE:
            if status_at is not None or status_by is not None or reason is not None:
                raise ValueError
        else:
            if status_at is None or status_by is None or reason is None:
                raise ValueError
            _utc(status_at, "stored status_at")
            _actor(status_by, "stored status_by")
            _reason(reason)
        return RegistryRecord(
            attestation,
            qualification,
            registered_at,
            registered_by,
            status,
            status_at,
            status_by,
            reason,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ModelRegistryError):
            raise
        raise ModelRegistryError("stored qualification failed integrity validation") from exc


def _verify_attestation(
    value: dict[str, Any],
) -> tuple[dict[str, Any], ModelQualification, datetime]:
    try:
        if not isinstance(value, dict) or set(value) != _ATTESTATION_FIELDS:
            raise ValueError
        document = json.loads(_canonical(value))
        if document["schema_version"] != "1.0" or document["evidence_count"] != 7:
            raise ValueError
        if not isinstance(document["qualification"], dict):
            raise ValueError
        q = document["qualification"]
        evaluations = tuple(
            ModelEvaluation(
                item["evaluation_id"],
                EvaluationCategory(item["category"]),
                EvaluationResult(item["result"]),
                tuple(UUID(identifier) for identifier in item["evidence_ids"]),
                tuple(item.get("limitations", ())),
            )
            for item in q["evaluations"]
        )
        evaluated_at = _parse_time(q["evaluated_at"])
        expires_at = _parse_time(q["expires_at"])
        validity = int((expires_at - evaluated_at).total_seconds())
        qualification = qualify_model(
            qualification_id=UUID(q["qualification_id"]),
            provider_id=q["provider_id"],
            model_id=q["model_id"],
            adapter_version=q["adapter_version"],
            evaluated_at=evaluated_at,
            validity_seconds=validity,
            evaluations=evaluations,
        )
        if qualification.to_dict() != q:
            raise ValueError
        attested_at = _parse_time(document["attested_at"])
        if qualification.evaluated_at != attested_at:
            raise ValueError
        unsigned = {key: item for key, item in document.items() if key != "attestation_digest"}
        if _sha256(_canonical(unsigned)) != document["attestation_digest"]:
            raise ValueError
        producers = document["attestor_producers"]
        if not isinstance(producers, list) or not producers:
            raise ValueError
        for producer in producers:
            _actor(producer, "attestor producer")
        return document, qualification, attested_at
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ModelRegistryError):
            raise
        raise ModelRegistryError("attested qualification failed canonical verification") from exc


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _utc(parsed, "timestamp")
    return parsed


def _actor(value: object, field: str) -> None:
    if not isinstance(value, str) or not _ACTOR.fullmatch(value):
        raise ModelRegistryError(f"{field} is invalid")


def _reason(value: object) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 1000
        or redact(value) != value
        or any(ord(char) < 32 and char not in "\t\n\r" for char in value)
    ):
        raise ModelRegistryError("revocation reason is invalid or contains secret-like material")


def _utc(value: datetime, field: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise ModelRegistryError(f"{field} must be timezone-aware UTC")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
