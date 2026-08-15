"""Atomic durable NEXUS Agent sessions and candidate specification revisions."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from nexus_os.secrets import redact

_PROJECT = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_ACCEPTANCE = re.compile(r"^AC-[A-Z0-9][A-Z0-9_-]{1,63}$")
_ACTOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
_ARTIFACT = re.compile(r"^artifact:[A-Za-z0-9_./-]{1,240}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_CANDIDATE_FIELDS = {
    "schema_version",
    "candidate_id",
    "session_id",
    "revision",
    "objective",
    "mode",
    "inputs",
    "constraints",
    "acceptance_criteria",
    "required_capabilities",
    "risk_summary",
    "unresolved_questions",
    "review_ready",
    "candidate_digest",
}


class AgentStoreError(ValueError):
    """Safe Agent store validation, state, conflict, or integrity failure."""


class AgentStoreConflict(AgentStoreError):
    """Optimistic session sequence conflict."""


class AgentState(StrEnum):
    DRAFTING = "DRAFTING"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    SPECIFICATION_READY = "SPECIFICATION_READY"
    USER_REVIEW = "USER_REVIEW"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentEventType(StrEnum):
    SESSION_CREATED = "SESSION_CREATED"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    CLARIFICATION_RECEIVED = "CLARIFICATION_RECEIVED"
    SPECIFICATION_PREPARED = "SPECIFICATION_PREPARED"
    REVIEW_STARTED = "REVIEW_STARTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    SPECIFICATION_REVISED = "SPECIFICATION_REVISED"
    SPECIFICATION_APPROVED = "SPECIFICATION_APPROVED"
    RUN_STARTED = "RUN_STARTED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_FAILED = "SESSION_FAILED"


class AgentActorType(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
    REVIEWER = "REVIEWER"


@dataclass(frozen=True, slots=True)
class ReviewPrincipal:
    actor_id: str
    authenticated: bool
    authorized: bool

    def __post_init__(self) -> None:
        _actor(self.actor_id)
        if not isinstance(self.authenticated, bool) or not isinstance(self.authorized, bool):
            raise AgentStoreError("review principal flags must be boolean")


@dataclass(frozen=True, slots=True)
class CandidateSpecification:
    document: dict[str, Any]

    @property
    def candidate_id(self) -> UUID:
        return UUID(self.document["candidate_id"])

    @property
    def session_id(self) -> UUID:
        return UUID(self.document["session_id"])

    @property
    def revision(self) -> int:
        return int(self.document["revision"])

    @property
    def digest(self) -> str:
        return str(self.document["candidate_digest"])

    @property
    def review_ready(self) -> bool:
        return bool(self.document["review_ready"])

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(_canonical(self.document)))

    @classmethod
    def parse(cls, value: dict[str, Any]) -> CandidateSpecification:
        try:
            if not isinstance(value, dict) or set(value) != _CANDIDATE_FIELDS:
                raise ValueError
            document = json.loads(_canonical(value))
            if document["schema_version"] != "1.0":
                raise ValueError
            UUID(document["candidate_id"])
            UUID(document["session_id"])
            revision = document["revision"]
            if (
                not isinstance(revision, int)
                or isinstance(revision, bool)
                or not 1 <= revision <= 10000
            ):
                raise ValueError
            _text(document["objective"], 8000)
            if document["mode"] not in {"app_build", "research", "data_analysis"}:
                raise ValueError
            _string_list(document["inputs"], 256, 250, pattern=_ARTIFACT, unique=True)
            _string_list(document["constraints"], 256, 2000)
            _string_list(
                document["required_capabilities"], 128, 127, pattern=_CAPABILITY, unique=True
            )
            _string_list(document["unresolved_questions"], 64, 2000)
            criteria = document["acceptance_criteria"]
            if not isinstance(criteria, list) or not 1 <= len(criteria) <= 256:
                raise ValueError
            acceptance_ids = []
            for item in criteria:
                if not isinstance(item, dict) or set(item) != {
                    "acceptance_id",
                    "statement",
                    "verification_method",
                }:
                    raise ValueError
                if not _ACCEPTANCE.fullmatch(item["acceptance_id"]):
                    raise ValueError
                acceptance_ids.append(item["acceptance_id"])
                _text(item["statement"], 2000)
                _text(item["verification_method"], 2000)
            if len(acceptance_ids) != len(set(acceptance_ids)):
                raise ValueError
            risk = document["risk_summary"]
            if not isinstance(risk, dict) or set(risk) != {"highest_effect", "reasons"}:
                raise ValueError
            if risk["highest_effect"] not in {
                "READ_ONLY",
                "WORKSPACE_WRITE",
                "SENSITIVE",
                "DESTRUCTIVE",
            }:
                raise ValueError
            _string_list(risk["reasons"], 64, 1000)
            if not isinstance(document["review_ready"], bool):
                raise ValueError
            if document["review_ready"] and document["unresolved_questions"]:
                raise ValueError
            if redact(document) != document:
                raise ValueError
            declared = document["candidate_digest"]
            if not isinstance(declared, str) or not _DIGEST.fullmatch(declared):
                raise ValueError
            unsigned = {key: item for key, item in document.items() if key != "candidate_digest"}
            if hashlib.sha256(_canonical(unsigned)).hexdigest() != declared:
                raise ValueError
            return cls(document)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AgentStoreError("candidate specification failed canonical validation") from exc


@dataclass(frozen=True, slots=True)
class AgentEvent:
    event_id: UUID
    session_id: UUID
    sequence: int
    occurred_at: datetime
    from_state: AgentState | None
    to_state: AgentState
    event_type: AgentEventType
    actor_type: AgentActorType
    summary: str
    candidate_digest: str | None = None
    run_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": "1.0",
            "event_id": str(self.event_id),
            "session_id": str(self.session_id),
            "sequence": self.sequence,
            "occurred_at": _timestamp(self.occurred_at),
            "from_state": None if self.from_state is None else self.from_state.value,
            "to_state": self.to_state.value,
            "event_type": self.event_type.value,
            "actor_type": self.actor_type.value,
            "summary": self.summary,
        }
        if self.candidate_digest is not None:
            value["candidate_digest"] = self.candidate_digest
        if self.run_id is not None:
            value["run_id"] = str(self.run_id)
        return value


@dataclass(frozen=True, slots=True)
class AgentSession:
    session_id: UUID
    project_id: str
    state: AgentState
    created_at: datetime
    updated_at: datetime
    events: tuple[AgentEvent, ...]
    candidate_id: UUID | None = None
    approved_candidate_digest: str | None = None
    run_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": "1.0",
            "session_id": str(self.session_id),
            "project_id": self.project_id,
            "state": self.state.value,
            "created_at": _timestamp(self.created_at),
            "updated_at": _timestamp(self.updated_at),
            "events": [item.to_dict() for item in self.events],
        }
        if self.candidate_id is not None:
            value["candidate_id"] = str(self.candidate_id)
        if self.approved_candidate_digest is not None:
            value["approved_candidate_digest"] = self.approved_candidate_digest
        if self.run_id is not None:
            value["run_id"] = str(self.run_id)
        return value


class AgentSessionStore:
    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript("""
        CREATE TABLE IF NOT EXISTS agent_sessions (
          session_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, objective TEXT NOT NULL,
          state TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          sequence INTEGER NOT NULL, candidate_id TEXT, candidate_digest TEXT,
          approved_candidate_digest TEXT);
        CREATE TABLE IF NOT EXISTS agent_events (
          event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, sequence INTEGER NOT NULL,
          occurred_at TEXT NOT NULL, from_state TEXT, to_state TEXT NOT NULL,
          event_type TEXT NOT NULL, actor_type TEXT NOT NULL, actor_id TEXT NOT NULL,
          summary TEXT NOT NULL, candidate_digest TEXT,
          UNIQUE(session_id, sequence));
        CREATE TABLE IF NOT EXISTS agent_candidates (
          candidate_id TEXT NOT NULL, session_id TEXT NOT NULL, revision INTEGER NOT NULL,
          candidate_digest TEXT NOT NULL UNIQUE, document_json TEXT NOT NULL,
          created_at TEXT NOT NULL, PRIMARY KEY(candidate_id, revision));
        CREATE TRIGGER IF NOT EXISTS no_agent_event_update BEFORE UPDATE ON agent_events
          BEGIN SELECT RAISE(ABORT, 'agent events are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS no_agent_event_delete BEFORE DELETE ON agent_events
          BEGIN SELECT RAISE(ABORT, 'agent events are append only'); END;
        CREATE TRIGGER IF NOT EXISTS no_agent_candidate_update BEFORE UPDATE ON agent_candidates
          BEGIN SELECT RAISE(ABORT, 'agent candidates are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS no_agent_candidate_delete BEFORE DELETE ON agent_candidates
          BEGIN SELECT RAISE(ABORT, 'agent candidates are append only'); END;
        """)
        session_columns = {
            str(row[1]) for row in self._connection.execute("PRAGMA table_info(agent_sessions)")
        }
        if "run_id" not in session_columns:
            self._connection.execute("ALTER TABLE agent_sessions ADD COLUMN run_id TEXT")
        event_columns = {
            str(row[1]) for row in self._connection.execute("PRAGMA table_info(agent_events)")
        }
        if "run_id" not in event_columns:
            self._connection.execute("ALTER TABLE agent_events ADD COLUMN run_id TEXT")

    def close(self) -> None:
        self._connection.close()

    def create(
        self,
        *,
        session_id: UUID,
        event_id: UUID,
        project_id: str,
        objective: str,
        actor_id: str,
        occurred_at: datetime,
    ) -> AgentSession:
        if not isinstance(session_id, UUID) or not isinstance(event_id, UUID):
            raise AgentStoreError("session_id and event_id must be UUID values")
        if not isinstance(project_id, str) or not _PROJECT.fullmatch(project_id):
            raise AgentStoreError("project_id is invalid")
        _text(objective, 8000)
        _actor(actor_id)
        _utc(occurred_at)
        if redact(objective) != objective:
            raise AgentStoreError("objective contains secret-like material")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                """INSERT INTO agent_sessions
                (session_id, project_id, objective, state, created_at, updated_at,
                 sequence, candidate_id, candidate_digest, approved_candidate_digest, run_id)
                VALUES (?, ?, ?, ?, ?, ?, 1, NULL, NULL, NULL, NULL)""",
                (
                    str(session_id),
                    project_id,
                    objective,
                    AgentState.DRAFTING.value,
                    occurred_at.isoformat(),
                    occurred_at.isoformat(),
                ),
            )
            self._insert_event(
                event_id,
                session_id,
                1,
                occurred_at,
                None,
                AgentState.DRAFTING,
                AgentEventType.SESSION_CREATED,
                AgentActorType.USER,
                actor_id,
                "Agent session created.",
                None,
            )
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise AgentStoreError("session or event already exists") from exc
        return self.get(session_id)

    def save_candidate(
        self,
        candidate: CandidateSpecification,
        *,
        event_id: UUID,
        actor_id: str,
        occurred_at: datetime,
        expected_sequence: int,
    ) -> AgentSession:
        _actor(actor_id)
        _utc(occurred_at)
        if not isinstance(candidate, CandidateSpecification):
            raise AgentStoreError("candidate must be a CandidateSpecification")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._locked(candidate.session_id, expected_sequence, AgentState.DRAFTING)
            prior = self._connection.execute(
                "SELECT candidate_id, MAX(revision) FROM agent_candidates WHERE session_id = ?",
                (str(candidate.session_id),),
            ).fetchone()
            if prior[0] is not None and (
                str(candidate.candidate_id) != str(prior[0])
                or candidate.revision != int(prior[1]) + 1
            ):
                raise AgentStoreError("candidate identity or revision is not monotonic")
            if prior[0] is None and candidate.revision != 1:
                raise AgentStoreError("first candidate revision must be 1")
            if occurred_at < datetime.fromisoformat(str(row[5])):
                raise AgentStoreError("event chronology is invalid")
            self._connection.execute(
                "INSERT INTO agent_candidates VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(candidate.candidate_id),
                    str(candidate.session_id),
                    candidate.revision,
                    candidate.digest,
                    _canonical(candidate.document).decode(),
                    occurred_at.isoformat(),
                ),
            )
            target = (
                AgentState.SPECIFICATION_READY
                if candidate.review_ready
                else AgentState.CLARIFICATION_REQUIRED
            )
            event_type = (
                AgentEventType.SPECIFICATION_PREPARED
                if candidate.review_ready
                else AgentEventType.CLARIFICATION_REQUESTED
            )
            summary = (
                "Candidate specification passed structural validation."
                if candidate.review_ready
                else "Candidate specification requires clarification."
            )
            self._advance(
                row,
                event_id,
                occurred_at,
                target,
                event_type,
                AgentActorType.AGENT,
                actor_id,
                summary,
                candidate.digest,
                candidate.candidate_id,
            )
            self._connection.execute("COMMIT")
        except Exception:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise
        return self.get(candidate.session_id)

    def receive_clarification(
        self,
        session_id: UUID,
        *,
        event_id: UUID,
        actor_id: str,
        occurred_at: datetime,
        expected_sequence: int,
    ) -> AgentSession:
        return self._simple_transition(
            session_id,
            event_id,
            actor_id,
            occurred_at,
            expected_sequence,
            AgentState.CLARIFICATION_REQUIRED,
            AgentState.DRAFTING,
            AgentEventType.CLARIFICATION_RECEIVED,
            AgentActorType.USER,
            "Clarification received; candidate revision required.",
        )

    def request_revision(
        self,
        session_id: UUID,
        *,
        event_id: UUID,
        actor_id: str,
        occurred_at: datetime,
        expected_sequence: int,
    ) -> AgentSession:
        """Return an unapproved review candidate to drafting for one immutable revision."""
        return self._simple_transition(
            session_id,
            event_id,
            actor_id,
            occurred_at,
            expected_sequence,
            AgentState.USER_REVIEW,
            AgentState.DRAFTING,
            AgentEventType.REVISION_REQUESTED,
            AgentActorType.USER,
            "Candidate revision requested by the authenticated operator.",
        )

    def start_review(
        self,
        session_id: UUID,
        *,
        event_id: UUID,
        actor_id: str,
        occurred_at: datetime,
        expected_sequence: int,
    ) -> AgentSession:
        return self._simple_transition(
            session_id,
            event_id,
            actor_id,
            occurred_at,
            expected_sequence,
            AgentState.SPECIFICATION_READY,
            AgentState.USER_REVIEW,
            AgentEventType.REVIEW_STARTED,
            AgentActorType.SYSTEM,
            "Candidate presented for authorized review.",
            bind_candidate=True,
        )

    def approve(
        self,
        session_id: UUID,
        *,
        event_id: UUID,
        candidate_digest: str,
        principal: ReviewPrincipal,
        occurred_at: datetime,
        expected_sequence: int,
    ) -> AgentSession:
        if not principal.authenticated or not principal.authorized:
            raise AgentStoreError("authenticated authorized reviewer is required")
        if not isinstance(candidate_digest, str) or not _DIGEST.fullmatch(candidate_digest):
            raise AgentStoreError("candidate digest is invalid")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._locked(session_id, expected_sequence, AgentState.USER_REVIEW)
            if row[8] != candidate_digest:
                raise AgentStoreError("approval candidate digest does not match current revision")
            self._advance(
                row,
                event_id,
                occurred_at,
                AgentState.APPROVED,
                AgentEventType.SPECIFICATION_APPROVED,
                AgentActorType.REVIEWER,
                principal.actor_id,
                "Candidate specification approved.",
                candidate_digest,
                None,
                approved_digest=candidate_digest,
            )
            self._connection.execute("COMMIT")
        except Exception:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise
        return self.get(session_id)

    def start_run(
        self,
        session_id: UUID,
        *,
        event_id: UUID,
        run_id: UUID,
        candidate_digest: str,
        actor_id: str,
        occurred_at: datetime,
        expected_sequence: int,
    ) -> AgentSession:
        """Bind exactly one initialized runtime run to an approved candidate."""
        if not isinstance(run_id, UUID):
            raise AgentStoreError("run_id must be a UUID")
        if not isinstance(candidate_digest, str) or not _DIGEST.fullmatch(candidate_digest):
            raise AgentStoreError("candidate digest is invalid")
        _actor(actor_id)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._locked(session_id, expected_sequence, AgentState.APPROVED)
            if row[9] != candidate_digest or row[8] != candidate_digest:
                raise AgentStoreError("run candidate digest does not match approved revision")
            if len(row) > 10 and row[10] is not None:
                raise AgentStoreError("Agent session already has a runtime run")
            self._advance(
                row,
                event_id,
                occurred_at,
                AgentState.RUNNING,
                AgentEventType.RUN_STARTED,
                AgentActorType.SYSTEM,
                actor_id,
                "Approved candidate bound to initialized runtime run.",
                candidate_digest,
                None,
                run_id=run_id,
            )
            self._connection.execute("COMMIT")
        except Exception:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise
        return self.get(session_id)

    def start_verification(
        self,
        session_id: UUID,
        *,
        event_id: UUID,
        actor_id: str,
        occurred_at: datetime,
        expected_sequence: int,
    ) -> AgentSession:
        return self._simple_transition(
            session_id,
            event_id,
            actor_id,
            occurred_at,
            expected_sequence,
            AgentState.RUNNING,
            AgentState.VERIFYING,
            AgentEventType.VERIFICATION_STARTED,
            AgentActorType.SYSTEM,
            "Runtime succeeded; acceptance verification started.",
        )

    def complete_verification(
        self,
        session_id: UUID,
        *,
        event_id: UUID,
        actor_id: str,
        occurred_at: datetime,
        expected_sequence: int,
        passed: bool,
    ) -> AgentSession:
        return self._simple_transition(
            session_id,
            event_id,
            actor_id,
            occurred_at,
            expected_sequence,
            AgentState.VERIFYING,
            AgentState.COMPLETED if passed else AgentState.FAILED,
            AgentEventType.SESSION_COMPLETED if passed else AgentEventType.SESSION_FAILED,
            AgentActorType.SYSTEM,
            "All approved acceptance criteria passed."
            if passed
            else "Acceptance verification failed.",
        )

    def get_candidate(self, session_id: UUID) -> CandidateSpecification:
        row = self._connection.execute(
            """SELECT document_json FROM agent_candidates
               WHERE session_id = ? ORDER BY revision DESC LIMIT 1""",
            (str(session_id),),
        ).fetchone()
        if row is None:
            raise AgentStoreError("candidate not found")
        try:
            return CandidateSpecification.parse(json.loads(str(row[0])))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AgentStoreError("stored candidate failed integrity validation") from exc

    def objective(self, session_id: UUID) -> str:
        row = self._connection.execute(
            "SELECT objective FROM agent_sessions WHERE session_id = ?", (str(session_id),)
        ).fetchone()
        if row is None:
            raise AgentStoreError("session not found")
        value = str(row[0])
        try:
            _text(value, 8000)
        except ValueError as exc:
            raise AgentStoreError("stored Agent objective failed integrity validation") from exc
        if redact(value) != value:
            raise AgentStoreError("stored Agent objective failed integrity validation")
        return value

    def get(self, session_id: UUID) -> AgentSession:
        row = self._connection.execute(
            "SELECT * FROM agent_sessions WHERE session_id = ?", (str(session_id),)
        ).fetchone()
        if row is None:
            raise AgentStoreError("session not found")
        event_rows = self._connection.execute(
            "SELECT * FROM agent_events WHERE session_id = ? ORDER BY sequence", (str(session_id),)
        ).fetchall()
        try:
            events = tuple(_event(item) for item in event_rows)
            if (
                [item.sequence for item in events] != list(range(1, int(row[6]) + 1))
                or not events
                or events[-1].to_state.value != row[3]
            ):
                raise ValueError
            return AgentSession(
                UUID(str(row[0])),
                str(row[1]),
                AgentState(str(row[3])),
                datetime.fromisoformat(str(row[4])),
                datetime.fromisoformat(str(row[5])),
                events,
                None if row[7] is None else UUID(str(row[7])),
                None if row[9] is None else str(row[9]),
                None if len(row) <= 10 or row[10] is None else UUID(str(row[10])),
            )
        except (ValueError, TypeError) as exc:
            raise AgentStoreError("stored Agent session failed integrity validation") from exc

    def _simple_transition(
        self,
        session_id: UUID,
        event_id: UUID,
        actor_id: str,
        occurred_at: datetime,
        expected_sequence: int,
        source: AgentState,
        target: AgentState,
        event_type: AgentEventType,
        actor_type: AgentActorType,
        summary: str,
        bind_candidate: bool = False,
    ) -> AgentSession:
        _actor(actor_id)
        _utc(occurred_at)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._locked(session_id, expected_sequence, source)
            digest = str(row[8]) if bind_candidate else None
            self._advance(
                row,
                event_id,
                occurred_at,
                target,
                event_type,
                actor_type,
                actor_id,
                summary,
                digest,
                None,
            )
            self._connection.execute("COMMIT")
        except Exception:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            raise
        return self.get(session_id)

    def _locked(
        self, session_id: UUID, expected_sequence: int, state: AgentState
    ) -> tuple[object, ...]:
        row = self._connection.execute(
            "SELECT * FROM agent_sessions WHERE session_id = ?", (str(session_id),)
        ).fetchone()
        if row is None:
            raise AgentStoreError("session not found")
        if int(str(row[6])) != expected_sequence:
            raise AgentStoreConflict("Agent session sequence conflict")
        if row[3] != state.value:
            raise AgentStoreError("Agent session state does not permit operation")
        return cast(tuple[object, ...], row)

    def _advance(
        self,
        row: tuple[object, ...],
        event_id: UUID,
        occurred_at: datetime,
        target: AgentState,
        event_type: AgentEventType,
        actor_type: AgentActorType,
        actor_id: str,
        summary: str,
        digest: str | None,
        candidate_id: UUID | None,
        approved_digest: str | None = None,
        run_id: UUID | None = None,
    ) -> None:
        _utc(occurred_at)
        if occurred_at < datetime.fromisoformat(str(row[5])):
            raise AgentStoreError("event chronology is invalid")
        sequence = int(str(row[6])) + 1
        self._insert_event(
            event_id,
            UUID(str(row[0])),
            sequence,
            occurred_at,
            AgentState(str(row[3])),
            target,
            event_type,
            actor_type,
            actor_id,
            summary,
            digest,
            run_id,
        )
        self._connection.execute(
            """UPDATE agent_sessions SET state=?, updated_at=?, sequence=?,
            candidate_id=COALESCE(?, candidate_id), candidate_digest=COALESCE(?, candidate_digest),
            approved_candidate_digest=COALESCE(?, approved_candidate_digest),
            run_id=COALESCE(?, run_id) WHERE session_id=?""",
            (
                target.value,
                occurred_at.isoformat(),
                sequence,
                None if candidate_id is None else str(candidate_id),
                digest,
                approved_digest,
                None if run_id is None else str(run_id),
                row[0],
            ),
        )

    def _insert_event(
        self,
        event_id: UUID,
        session_id: UUID,
        sequence: int,
        occurred_at: datetime,
        source: AgentState | None,
        target: AgentState,
        event_type: AgentEventType,
        actor_type: AgentActorType,
        actor_id: str,
        summary: str,
        digest: str | None,
        run_id: UUID | None = None,
    ) -> None:
        if not isinstance(event_id, UUID):
            raise AgentStoreError("event_id must be a UUID")
        _text(summary, 2000)
        self._connection.execute(
            """INSERT INTO agent_events
            (event_id, session_id, sequence, occurred_at, from_state, to_state,
             event_type, actor_type, actor_id, summary, candidate_digest, run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(event_id),
                str(session_id),
                sequence,
                occurred_at.isoformat(),
                None if source is None else source.value,
                target.value,
                event_type.value,
                actor_type.value,
                actor_id,
                summary,
                digest,
                None if run_id is None else str(run_id),
            ),
        )


def candidate_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _event(row: tuple[object, ...]) -> AgentEvent:
    return AgentEvent(
        UUID(str(row[0])),
        UUID(str(row[1])),
        int(str(row[2])),
        datetime.fromisoformat(str(row[3])),
        None if row[4] is None else AgentState(str(row[4])),
        AgentState(str(row[5])),
        AgentEventType(str(row[6])),
        AgentActorType(str(row[7])),
        str(row[9]),
        None if row[10] is None else str(row[10]),
        None if len(row) <= 11 or row[11] is None else UUID(str(row[11])),
    )


def _string_list(
    value: object,
    maximum_items: int,
    maximum_text: int,
    *,
    pattern: re.Pattern[str] | None = None,
    unique: bool = False,
) -> None:
    if not isinstance(value, list) or len(value) > maximum_items:
        raise ValueError
    for item in value:
        _text(item, maximum_text)
        if pattern is not None and not pattern.fullmatch(item):
            raise ValueError
    if unique and len(value) != len(set(value)):
        raise ValueError


def _text(value: object, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or any(ord(char) < 32 and char not in "\t\n\r" for char in value)
    ):
        raise ValueError


def _actor(value: object) -> None:
    if not isinstance(value, str) or not _ACTOR.fullmatch(value):
        raise AgentStoreError("actor identifier is invalid")


def _utc(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise AgentStoreError("timestamp must be timezone-aware UTC")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
