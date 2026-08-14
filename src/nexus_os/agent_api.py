"""Authenticated transport-neutral application API for NEXUS Agent."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, cast
from uuid import UUID

from nexus_os.agent_controller import AgentControllerError, AgentReasoningController
from nexus_os.agent_store import AgentSessionStore, AgentStoreError, ReviewPrincipal
from nexus_os.domain import TraceId
from nexus_os.model_registry import ModelRegistryError, RegistryRecord
from nexus_os.secrets import redact

_TOKEN = re.compile(r"^Bearer ([\x21-\x7e]{16,4096})$")
_KEY = re.compile(r"^[\x21-\x7e]{16,128}$")
_ACTOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
_PATH = re.compile(r"^/v1/[A-Za-z0-9/_-]*$")
_MAX_BODY = 1024 * 1024
_SCOPES = frozenset(
    {
        "agent:read",
        "agent:write",
        "agent:approve",
        "agent:execute",
        "agent:verify",
        "model-qualifications:read",
    }
)


class AgentApiError(ValueError):
    """Safe Agent API validation or application failure."""


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    actor_id: str
    scopes: frozenset[str]
    human: bool

    def __post_init__(self) -> None:
        if not _ACTOR.fullmatch(self.actor_id) or not self.scopes <= _SCOPES:
            raise AgentApiError("authenticated identity is invalid")
        if not isinstance(self.human, bool):
            raise AgentApiError("authenticated identity type is invalid")


class BearerAuthenticator(Protocol):
    def authenticate(self, token: str) -> AgentIdentity | None: ...


class QualificationReader(Protocol):
    def active(self, *, at: datetime) -> tuple[RegistryRecord, ...]: ...


class ApplicationIds(Protocol):
    def session_id(self) -> UUID: ...
    def event_id(self) -> UUID: ...


class AgentRuntimeApi(Protocol):
    def start(
        self,
        session_id: UUID,
        identity: AgentIdentity,
        request: AgentApiRequest,
        body: dict[str, Any],
    ) -> Mapping[str, Any]: ...
    def status(self, session_id: UUID) -> Mapping[str, Any]: ...
    def preview(
        self, session_id: UUID, identity: AgentIdentity, task_id: str | None = None
    ) -> Mapping[str, Any]: ...
    async def prepare(
        self,
        session_id: UUID,
        identity: AgentIdentity,
        request: AgentApiRequest,
        body: dict[str, Any] | None,
    ) -> Mapping[str, Any]: ...
    def evidence(self, session_id: UUID) -> Mapping[str, Any]: ...
    async def tick(
        self,
        session_id: UUID,
        identity: AgentIdentity,
        request: AgentApiRequest,
        body: dict[str, Any] | None,
    ) -> Mapping[str, Any]: ...
    def decide_approval(
        self,
        session_id: UUID,
        approval_id: UUID,
        identity: AgentIdentity,
        request: AgentApiRequest,
        body: dict[str, Any],
    ) -> Mapping[str, Any]: ...
    def verify(
        self, session_id: UUID, identity: AgentIdentity, request: AgentApiRequest
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class AgentApiRequest:
    method: str
    path: str
    headers: Mapping[str, str]
    body: Mapping[str, Any] | None
    request_id: str
    occurred_at: datetime
    trace_id: TraceId

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True, slots=True)
class AgentApiResponse:
    status: int
    body: Mapping[str, Any] | list[Any]
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _Route:
    method: str
    pattern: re.Pattern[str]
    operation: str
    scope: str
    mutation: bool


_ROUTES = (
    _Route("POST", re.compile(r"^/v1/agent/sessions$"), "create", "agent:write", True),
    _Route(
        "POST",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/runtime/preparations$"),
        "runtime_prepare",
        "agent:execute",
        True,
    ),
    _Route(
        "GET",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)$"),
        "get",
        "agent:read",
        False,
    ),
    _Route(
        "POST",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/runtime$"),
        "runtime_start",
        "agent:execute",
        True,
    ),
    _Route(
        "GET",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/runtime$"),
        "runtime_status",
        "agent:read",
        False,
    ),
    _Route(
        "GET",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/runtime/preview$"),
        "runtime_preview",
        "agent:read",
        False,
    ),
    _Route(
        "GET",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/runtime/evidence$"),
        "runtime_evidence",
        "agent:read",
        False,
    ),
    _Route(
        "POST",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/runtime/ticks$"),
        "runtime_tick",
        "agent:execute",
        True,
    ),
    _Route(
        "POST",
        re.compile(
            r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/runtime/approvals/(?P<approvalId>[^/]+)$"
        ),
        "runtime_approval",
        "agent:approve",
        True,
    ),
    _Route(
        "POST",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/runtime/verify$"),
        "runtime_verify",
        "agent:verify",
        True,
    ),
    _Route(
        "POST",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/clarifications$"),
        "clarify",
        "agent:write",
        True,
    ),
    _Route(
        "GET",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/candidate$"),
        "candidate",
        "agent:read",
        False,
    ),
    _Route(
        "POST",
        re.compile(r"^/v1/agent/sessions/(?P<sessionId>[^/]+)/approve$"),
        "approve",
        "agent:approve",
        True,
    ),
    _Route(
        "GET",
        re.compile(r"^/v1/model-qualifications$"),
        "models",
        "model-qualifications:read",
        False,
    ),
)


class DurableReplayStore:
    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript("""
        CREATE TABLE IF NOT EXISTS agent_api_replays (
          actor_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, binding TEXT NOT NULL,
          status INTEGER NOT NULL, body_json TEXT NOT NULL, PRIMARY KEY(actor_id, idempotency_key));
        CREATE TRIGGER IF NOT EXISTS no_agent_replay_update BEFORE UPDATE ON agent_api_replays
          BEGIN SELECT RAISE(ABORT, 'agent API replays are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS no_agent_replay_delete BEFORE DELETE ON agent_api_replays
          BEGIN SELECT RAISE(ABORT, 'agent API replays are append only'); END;
        """)

    def close(self) -> None:
        self._connection.close()

    def find(self, actor_id: str, key: str, binding: str) -> AgentApiResponse | None:
        row = self._connection.execute(
            """SELECT binding, status, body_json FROM agent_api_replays
               WHERE actor_id=? AND idempotency_key=?""",
            (actor_id, key),
        ).fetchone()
        if row is None:
            return None
        if str(row[0]) != binding:
            raise AgentApiError("idempotency key conflicts with prior request")
        try:
            body = json.loads(str(row[2]))
            if not isinstance(body, (dict, list)):
                raise ValueError
            return AgentApiResponse(int(str(row[1])), body, {"Idempotent-Replay": "true"})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AgentApiError("stored idempotent response failed integrity validation") from exc

    def save(self, actor_id: str, key: str, binding: str, response: AgentApiResponse) -> None:
        encoded = _canonical(response.body)
        try:
            self._connection.execute(
                "INSERT INTO agent_api_replays VALUES (?, ?, ?, ?, ?)",
                (actor_id, key, binding, response.status, encoded),
            )
        except sqlite3.IntegrityError as exc:
            existing = self.find(actor_id, key, binding)
            if (
                existing is None
                or existing.status != response.status
                or _canonical(existing.body) != encoded
            ):
                raise AgentApiError("concurrent idempotent response conflict") from exc


class AgentApplicationService:
    def __init__(
        self,
        *,
        sessions: AgentSessionStore,
        controller: AgentReasoningController,
        qualifications: QualificationReader,
        ids: ApplicationIds,
        runtime: AgentRuntimeApi | None = None,
    ) -> None:
        self._sessions = sessions
        self._controller = controller
        self._qualifications = qualifications
        self._ids = ids
        self._runtime = runtime

    async def invoke(
        self,
        operation: str,
        values: Mapping[str, str],
        body: dict[str, Any] | None,
        identity: AgentIdentity,
        request: AgentApiRequest,
    ) -> tuple[int, Mapping[str, Any] | list[Any]]:
        if operation == "create":
            if body is None or set(body) != {"project_id", "objective"}:
                raise AgentApiError("request body is invalid")
            session_id = self._ids.session_id()
            session = self._sessions.create(
                session_id=session_id,
                event_id=self._ids.event_id(),
                project_id=body["project_id"],
                objective=body["objective"],
                actor_id=identity.actor_id,
                occurred_at=request.occurred_at,
            )
            prepared = await self._controller.prepare(
                session_id,
                actor_id="agent-controller",
                at=request.occurred_at,
                expected_sequence=len(session.events),
                trace_id=request.trace_id,
            )
            if prepared.state.value == "SPECIFICATION_READY":
                prepared = self._sessions.start_review(
                    session_id,
                    event_id=self._ids.event_id(),
                    actor_id="agent-service",
                    occurred_at=request.occurred_at,
                    expected_sequence=len(prepared.events),
                )
            return 201, prepared.to_dict()
        target_session_id = UUID(values["sessionId"]) if "sessionId" in values else None
        if operation.startswith("runtime_"):
            if self._runtime is None or target_session_id is None:
                raise AgentApiError("runtime API is unavailable")
            if operation == "runtime_start" and body is not None:
                return 201, self._runtime.start(target_session_id, identity, request, body)
            if operation == "runtime_status":
                return 200, self._runtime.status(target_session_id)
            if operation == "runtime_prepare":
                return 200, await self._runtime.prepare(target_session_id, identity, request, body)
            if operation == "runtime_preview":
                return 200, self._runtime.preview(target_session_id, identity)
            if operation == "runtime_evidence":
                return 200, self._runtime.evidence(target_session_id)
            if operation == "runtime_tick":
                return 200, await self._runtime.tick(target_session_id, identity, request, body)
            if operation == "runtime_approval" and body is not None:
                approval_id = UUID(values["approvalId"])
                return 200, self._runtime.decide_approval(
                    target_session_id, approval_id, identity, request, body
                )
            if operation == "runtime_verify":
                return 200, self._runtime.verify(target_session_id, identity, request)
            raise AgentApiError("runtime request body is invalid")
        if operation == "get" and target_session_id is not None:
            return 200, self._sessions.get(target_session_id).to_dict()
        if operation == "candidate" and target_session_id is not None:
            return 200, self._sessions.get_candidate(target_session_id).to_dict()
        if operation == "clarify" and target_session_id is not None:
            if body is None or set(body) != {"response"}:
                raise AgentApiError("request body is invalid")
            session = self._sessions.get(target_session_id)
            drafting = self._sessions.receive_clarification(
                target_session_id,
                event_id=self._ids.event_id(),
                actor_id=identity.actor_id,
                occurred_at=request.occurred_at,
                expected_sequence=len(session.events),
            )
            prepared = await self._controller.prepare(
                target_session_id,
                actor_id="agent-controller",
                at=request.occurred_at,
                expected_sequence=len(drafting.events),
                trace_id=request.trace_id,
                clarification=body["response"],
            )
            if prepared.state.value == "SPECIFICATION_READY":
                prepared = self._sessions.start_review(
                    target_session_id,
                    event_id=self._ids.event_id(),
                    actor_id="agent-service",
                    occurred_at=request.occurred_at,
                    expected_sequence=len(prepared.events),
                )
            return 200, prepared.to_dict()
        if operation == "approve" and target_session_id is not None:
            if body is None or set(body) != {"candidate_digest"}:
                raise AgentApiError("request body is invalid")
            session = self._sessions.get(target_session_id)
            approved = self._sessions.approve(
                target_session_id,
                event_id=self._ids.event_id(),
                candidate_digest=body["candidate_digest"],
                principal=ReviewPrincipal(identity.actor_id, True, identity.human),
                occurred_at=request.occurred_at,
                expected_sequence=len(session.events),
            )
            return 200, approved.to_dict()
        if operation == "models":
            return 200, [
                item.to_dict() for item in self._qualifications.active(at=request.occurred_at)
            ]
        raise AgentApiError("operation is not implemented")


class AgentApplication:
    def __init__(
        self,
        *,
        authenticator: BearerAuthenticator,
        service: AgentApplicationService,
        replays: DurableReplayStore,
    ) -> None:
        self._authenticator = authenticator
        self._service = service
        self._replays = replays

    async def handle(self, request: AgentApiRequest) -> AgentApiResponse:
        invalid = self._validate(request)
        if invalid is not None:
            return invalid
        match = _TOKEN.fullmatch(request.headers.get("Authorization", ""))
        identity = None if match is None else self._authenticator.authenticate(match.group(1))
        if identity is None:
            return _error(401, "unauthorized", "Authentication is required", request.request_id)
        route, values = self._route(request.method, request.path)
        if route is None:
            return _error(404, "not_found", "Resource not found", request.request_id)
        if route.scope not in identity.scopes:
            return _error(403, "forbidden", "Request is not authorized", request.request_id)
        try:
            body, digest = _body(request.body)
        except AgentApiError:
            return _error(400, "invalid_request", "Request body is invalid", request.request_id)
        if not _valid_operation_body(route.operation, body):
            return _error(400, "invalid_request", "Request body is invalid", request.request_id)
        key = request.headers.get("Idempotency-Key") if route.mutation else None
        binding = f"{route.operation}:{request.path}:{digest}"
        if route.mutation and (not isinstance(key, str) or not _KEY.fullmatch(key)):
            return _error(
                400,
                "invalid_idempotency_key",
                "Idempotency-Key is required",
                request.request_id,
            )
        if key is not None:
            try:
                replay = self._replays.find(identity.actor_id, key, binding)
            except AgentApiError:
                return _error(
                    409,
                    "idempotency_conflict",
                    "Idempotency-Key conflicts with prior request",
                    request.request_id,
                )
            if replay is not None:
                return replay
        try:
            status, output = await self._service.invoke(
                route.operation, values, body, identity, request
            )
            response = AgentApiResponse(status, output, {"X-Trace-Id": str(request.trace_id)})
        except AgentControllerError:
            response = _error(
                422,
                "proposal_rejected",
                "Agent proposal could not be validated",
                request.request_id,
            )
        except (AgentStoreError, ModelRegistryError, AgentApiError, ValueError):
            response = _error(
                409,
                "state_conflict",
                "Agent operation conflicts with current state",
                request.request_id,
            )
        except Exception:
            response = _error(
                500,
                "internal_error",
                "Internal service failure",
                request.request_id,
                True,
            )
        if key is not None and response.status < 500:
            try:
                self._replays.save(identity.actor_id, key, binding, response)
            except AgentApiError:
                return _error(
                    500,
                    "internal_error",
                    "Internal service failure",
                    request.request_id,
                    True,
                )
        return response

    @staticmethod
    def _validate(request: AgentApiRequest) -> AgentApiResponse | None:
        if (
            request.method not in {"GET", "POST"}
            or not _PATH.fullmatch(request.path)
            or ".." in request.path.split("/")
            or not isinstance(request.request_id, str)
            or not 1 <= len(request.request_id) <= 256
        ):
            return _error(400, "invalid_request", "Request envelope is invalid", "invalid")
        if request.occurred_at.tzinfo is None or request.occurred_at.utcoffset() != UTC.utcoffset(
            request.occurred_at
        ):
            return _error(
                400,
                "invalid_request",
                "Request envelope is invalid",
                request.request_id,
            )
        return None

    @staticmethod
    def _route(method: str, path: str) -> tuple[_Route | None, dict[str, str]]:
        for route in _ROUTES:
            match = route.pattern.fullmatch(path)
            if route.method == method and match is not None:
                values = match.groupdict()
                try:
                    for key in ("sessionId", "approvalId"):
                        if key in values:
                            UUID(values[key])
                except ValueError:
                    return None, {}
                return route, values
        return None, {}


def _body(value: Mapping[str, Any] | None) -> tuple[dict[str, Any] | None, str]:
    if value is None:
        return None, hashlib.sha256(b"null").hexdigest()
    if not isinstance(value, Mapping) or redact(value) != value:
        raise AgentApiError("invalid body")
    try:
        encoded = _canonical(value)
    except (TypeError, ValueError) as exc:
        raise AgentApiError("invalid body") from exc
    if len(encoded.encode()) > _MAX_BODY:
        raise AgentApiError("invalid body")
    decoded = json.loads(encoded)
    return cast(dict[str, Any], decoded), hashlib.sha256(encoded.encode()).hexdigest()


def _valid_operation_body(operation: str, body: dict[str, Any] | None) -> bool:
    if operation == "create":
        return (
            body is not None
            and set(body) == {"project_id", "objective"}
            and isinstance(body["project_id"], str)
            and isinstance(body["objective"], str)
        )
    if operation == "clarify":
        return body is not None and set(body) == {"response"} and isinstance(body["response"], str)
    if operation == "approve":
        return (
            body is not None
            and set(body) == {"candidate_digest"}
            and isinstance(body["candidate_digest"], str)
        )
    if operation == "runtime_start":
        return (
            body is not None
            and set(body) == {"workspace_root"}
            and isinstance(body["workspace_root"], str)
        )
    if operation == "runtime_prepare":
        return body is None or (set(body) == {"task_id"} and isinstance(body["task_id"], str))
    if operation == "runtime_tick":
        return body is None or (
            set(body) <= {"approval_id", "task_id"}
            and all(isinstance(value, str) for value in body.values())
        )
    if operation == "runtime_approval":
        return (
            body is not None
            and set(body) <= {"status", "reason"}
            and set(body) >= {"status"}
            and body["status"] in {"APPROVED", "DENIED"}
            and ("reason" not in body or isinstance(body["reason"], str))
        )
    if operation == "runtime_verify":
        return body is None
    return body is None


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _error(
    status: int, code: str, message: str, request_id: str, retryable: bool = False
) -> AgentApiResponse:
    return AgentApiResponse(
        status,
        {
            "code": code,
            "message": message,
            "request_id": request_id,
            "retryable": retryable,
        },
    )
