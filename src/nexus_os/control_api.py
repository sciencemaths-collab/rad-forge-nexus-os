"""Transport-neutral REST/OpenAPI control application boundary."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol

from nexus_os.domain import TraceId

_METHODS = frozenset({"GET", "POST"})
_IDEMPOTENCY = re.compile(r"^[\x21-\x7e]{16,128}$")
_PATH = re.compile(r"^/v1/[A-Za-z0-9/_-]*$")
_MAX_BODY = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ApiContext:
    actor_id: str
    scopes: frozenset[str]
    trace_id: TraceId

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, str) or not self.actor_id or len(self.actor_id) > 256:
            raise ValueError("actor_id is invalid")
        if not isinstance(self.scopes, frozenset) or not self.scopes <= {
            "api:read",
            "api:write",
            "approvals:decide",
        }:
            raise ValueError("API scopes are invalid")


@dataclass(frozen=True, slots=True)
class ApiRequest:
    method: str
    path: str
    headers: Mapping[str, str]
    body: Mapping[str, Any] | None
    request_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status: int
    body: Mapping[str, Any] | list[Any]
    headers: Mapping[str, str] = field(default_factory=dict)


class ControlService(Protocol):
    async def invoke(
        self,
        operation: str,
        path_values: Mapping[str, str],
        body: Mapping[str, Any] | None,
        context: ApiContext,
    ) -> tuple[int, Mapping[str, Any] | list[Any]]: ...


@dataclass(frozen=True, slots=True)
class _Route:
    method: str
    pattern: re.Pattern[str]
    operation: str
    write: bool


_ROUTES = (
    _Route("POST", re.compile(r"^/v1/projects$"), "createProject", True),
    _Route("GET", re.compile(r"^/v1/projects/(?P<projectId>[^/]+)$"), "getProject", False),
    _Route("POST", re.compile(r"^/v1/projects/(?P<projectId>[^/]+)/plan$"), "planProject", True),
    _Route("POST", re.compile(r"^/v1/runs$"), "createRun", True),
    _Route("GET", re.compile(r"^/v1/runs/(?P<runId>[^/]+)$"), "getRun", False),
    _Route("POST", re.compile(r"^/v1/runs/(?P<runId>[^/]+)/cancel$"), "cancelRun", True),
    _Route("POST", re.compile(r"^/v1/runs/(?P<runId>[^/]+)/resume$"), "resumeRun", True),
    _Route("GET", re.compile(r"^/v1/runs/(?P<runId>[^/]+)/evidence$"), "listEvidence", False),
    _Route("GET", re.compile(r"^/v1/approvals/(?P<approvalId>[^/]+)$"), "getApproval", False),
    _Route(
        "POST",
        re.compile(r"^/v1/approvals/(?P<approvalId>[^/]+)/decision$"),
        "decideApproval",
        True,
    ),
    _Route("GET", re.compile(r"^/v1/providers$"), "listProviders", False),
    _Route("GET", re.compile(r"^/v1/capabilities$"), "listCapabilities", False),
)


class ControlApplication:
    def __init__(self, service: ControlService) -> None:
        self._service = service
        self._replay: dict[tuple[str, str], tuple[str, ApiResponse]] = {}

    async def handle(self, request: ApiRequest, context: ApiContext) -> ApiResponse:
        validation = self._validate_request(request)
        if validation is not None:
            return validation
        route, values = self._match(request.method, request.path)
        if route is None:
            return self._error(404, "not_found", "Resource not found", request.request_id)
        scope = "api:write" if route.write else "api:read"
        if scope not in context.scopes:
            return self._error(403, "forbidden", "Request is not authorized", request.request_id)
        if route.operation == "decideApproval" and "approvals:decide" not in context.scopes:
            return self._error(403, "forbidden", "Request is not authorized", request.request_id)
        if not self._valid_path_values(values):
            return self._error(400, "invalid_path", "Path parameter is invalid", request.request_id)

        body, digest_or_error = self._body(request.body)
        if isinstance(digest_or_error, ApiResponse):
            return digest_or_error
        digest = digest_or_error
        replay_key: tuple[str, str] | None = None
        if route.write:
            key = request.headers.get("Idempotency-Key")
            if not isinstance(key, str) or _IDEMPOTENCY.fullmatch(key) is None:
                return self._error(
                    400,
                    "invalid_idempotency_key",
                    "Idempotency-Key is required",
                    request.request_id,
                )
            replay_key = (context.actor_id, key)
            bound = f"{route.operation}:{request.path}:{digest}"
            if replay_key in self._replay:
                prior_bound, prior = self._replay[replay_key]
                if prior_bound != bound:
                    return self._error(
                        409,
                        "idempotency_conflict",
                        "Idempotency-Key conflicts with prior request",
                        request.request_id,
                    )
                return ApiResponse(prior.status, prior.body, {"Idempotent-Replay": "true"})

        if route.operation == "createRun" and (
            body is None
            or set(body) != {"project_id"}
            or not isinstance(body.get("project_id"), str)
        ):
            return self._error(
                400, "invalid_request", "Request body is invalid", request.request_id
            )
        try:
            status, output = await self._service.invoke(route.operation, values, body, context)
            response = ApiResponse(status, output, {"X-Trace-Id": str(context.trace_id)})
        except Exception as exc:
            response = self._error(
                500, "internal_error", "Internal service failure", request.request_id, True
            )
            response = ApiResponse(
                response.status, response.body, {"X-Trace-Id": str(context.trace_id)}
            )
            del exc
        if replay_key is not None and response.status < 500:
            self._replay[replay_key] = (f"{route.operation}:{request.path}:{digest}", response)
        return response

    @staticmethod
    def _validate_request(request: ApiRequest) -> ApiResponse | None:
        if (
            request.method not in _METHODS
            or not isinstance(request.path, str)
            or _PATH.fullmatch(request.path) is None
            or ".." in request.path.split("/")
            or not isinstance(request.request_id, str)
            or not 1 <= len(request.request_id) <= 256
        ):
            return ControlApplication._error(
                400, "invalid_request", "Request envelope is invalid", "invalid"
            )
        return None

    @staticmethod
    def _match(method: str, path: str) -> tuple[_Route | None, dict[str, str]]:
        for route in _ROUTES:
            match = route.pattern.fullmatch(path)
            if route.method == method and match is not None:
                return route, match.groupdict()
        return None, {}

    @staticmethod
    def _valid_path_values(values: Mapping[str, str]) -> bool:
        for name, value in values.items():
            if not value or len(value) > 256:
                return False
            if name in {"runId", "approvalId"}:
                try:
                    uuid.UUID(value)
                except ValueError:
                    return False
        return True

    @staticmethod
    def _body(body: Mapping[str, Any] | None) -> tuple[dict[str, Any] | None, str | ApiResponse]:
        if body is None:
            return None, "sha256:" + hashlib.sha256(b"null").hexdigest()
        if not isinstance(body, Mapping):
            return None, ControlApplication._error(
                400, "invalid_request", "Request body is invalid", "invalid"
            )
        try:
            encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
            decoded = json.loads(encoded)
        except (TypeError, ValueError):
            return None, ControlApplication._error(
                400, "invalid_request", "Request body is invalid", "invalid"
            )
        if len(encoded.encode()) > _MAX_BODY:
            return None, ControlApplication._error(
                413, "payload_too_large", "Request body is too large", "invalid"
            )
        return decoded, "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()

    @staticmethod
    def _error(
        status: int, code: str, message: str, request_id: str, retryable: bool = False
    ) -> ApiResponse:
        return ApiResponse(
            status,
            {"code": code, "message": message, "request_id": request_id, "retryable": retryable},
        )


class MemoryControlService:
    """Deterministic application-service fixture, not a production repository."""

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}
        self.mutation_count = 0

    async def invoke(
        self,
        operation: str,
        path_values: Mapping[str, str],
        body: Mapping[str, Any] | None,
        context: ApiContext,
    ) -> tuple[int, Mapping[str, Any] | list[Any]]:
        if operation == "createRun" and body is not None:
            self.mutation_count += 1
            run_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"nexus:{body['project_id']}:{self.mutation_count}")
            )
            run = {"run_id": run_id, "project_id": body["project_id"], "state": "SPECIFYING"}
            self._runs[run_id] = run
            return 202, run
        if operation == "getRun":
            found_run = self._runs.get(path_values["runId"])
            if found_run is not None:
                return 200, found_run
            return 404, {
                "code": "not_found",
                "message": "Run not found",
                "request_id": "service",
                "retryable": False,
            }
        if operation in {"listProviders", "listCapabilities", "listEvidence"}:
            return 200, []
        return 404, {
            "code": "not_found",
            "message": "Resource not found",
            "request_id": "service",
            "retryable": False,
        }
