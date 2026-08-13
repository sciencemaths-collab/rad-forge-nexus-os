"""Local operator password verification and short-lived bearer sessions."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nexus_os.agent_api import AgentIdentity

_DEFAULT_SCOPES = frozenset(
    {
        "agent:read",
        "agent:write",
        "agent:approve",
        "agent:execute",
        "agent:verify",
        "model-qualifications:read",
    }
)


class OperatorAuthError(ValueError):
    """Safe local operator authentication failure."""


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    expires_at: datetime
    identity: AgentIdentity


class OperatorAuthenticator:
    def __init__(
        self,
        path: Path,
        *,
        session_ttl: timedelta = timedelta(hours=8),
        max_sessions: int = 128,
    ) -> None:
        if not timedelta(minutes=1) <= session_ttl <= timedelta(days=1):
            raise OperatorAuthError("session_ttl must be from one minute to one day")
        if not 1 <= max_sessions <= 1024:
            raise OperatorAuthError("max_sessions must be from 1 to 1024")
        self._connection = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS local_operators (
            actor_id TEXT PRIMARY KEY, salt BLOB NOT NULL, password_hash BLOB NOT NULL,
            scopes_json TEXT NOT NULL, human INTEGER NOT NULL)"""
        )
        self._ttl = session_ttl
        self._max_sessions = max_sessions
        self._sessions: dict[str, tuple[datetime, AgentIdentity]] = {}
        self._lock = threading.RLock()

    def is_bootstrapped(self) -> bool:
        with self._lock:
            return (
                self._connection.execute("SELECT 1 FROM local_operators LIMIT 1").fetchone()
                is not None
            )

    def bootstrap(self, password: str, *, actor_id: str = "local-owner") -> None:
        if not isinstance(password, str) or len(password) < 12 or len(password) > 1024:
            raise OperatorAuthError("bootstrap password must contain 12 to 1024 characters")
        with self._lock:
            if self.is_bootstrapped():
                raise OperatorAuthError("local operator is already bootstrapped")
            identity = AgentIdentity(actor_id, _DEFAULT_SCOPES, True)
            salt = secrets.token_bytes(16)
            password_hash = _derive(password, salt)
            self._connection.execute(
                "INSERT INTO local_operators VALUES (?, ?, ?, ?, 1)",
                (actor_id, salt, password_hash, json.dumps(sorted(identity.scopes))),
            )

    def login(self, password: str, *, now: datetime) -> IssuedSession:
        _utc(now)
        if not isinstance(password, str) or len(password) > 1024:
            raise OperatorAuthError("operator credentials are invalid")
        with self._lock:
            row = self._connection.execute("SELECT * FROM local_operators LIMIT 1").fetchone()
            if row is None:
                raise OperatorAuthError("local operator is not bootstrapped")
            candidate = _derive(password, bytes(row[1]))
            if not hmac.compare_digest(candidate, bytes(row[2])):
                raise OperatorAuthError("operator credentials are invalid")
            try:
                scopes = frozenset(json.loads(str(row[3])))
                identity = AgentIdentity(str(row[0]), scopes, bool(row[4]))
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                raise OperatorAuthError("stored operator identity is invalid") from exc
            self._purge(now)
            if len(self._sessions) >= self._max_sessions:
                raise OperatorAuthError("local session limit reached")
            token = secrets.token_urlsafe(32)
            expires_at = now + self._ttl
            self._sessions[_token_digest(token)] = (expires_at, identity)
            return IssuedSession(token, expires_at, identity)

    def authenticate(self, token: str) -> AgentIdentity | None:
        if not isinstance(token, str) or not 32 <= len(token) <= 256:
            return None
        now = datetime.now(UTC)
        with self._lock:
            self._purge(now)
            value = self._sessions.get(_token_digest(token))
            if value is None or now >= value[0]:
                return None
            return value[1]

    def revoke(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(_token_digest(token), None)

    def close(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._connection.close()

    def _purge(self, now: datetime) -> None:
        for digest, (expires_at, _) in tuple(self._sessions.items()):
            if now >= expires_at:
                del self._sessions[digest]


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise OperatorAuthError("authentication timestamp must be timezone-aware UTC")
