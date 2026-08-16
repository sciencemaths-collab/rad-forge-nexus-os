"""Typed async Python SDK over an injected control-plane HTTP transport."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

_KEY = re.compile(r"^[\x21-\x7e]{16,128}$")
_TRACE = re.compile(r"^[0-9a-f]{32}$")
_STATES = frozenset(
    {
        "SPECIFYING",
        "PLANNED",
        "RUNNING",
        "WAITING_APPROVAL",
        "VERIFYING",
        "REPAIRING",
        "QUALIFYING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }
)


class SdkValidationError(ValueError):
    """Local or remote contract validation failure."""


class ApiError(RuntimeError):
    def __init__(
        self, status: int, code: str, message: str, request_id: str, retryable: bool
    ) -> None:
        super().__init__(f"RAD Agent API error: {code}")
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id
        self.retryable = retryable


class HttpTransport(Protocol):
    async def send(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any] | list[Any], Mapping[str, str]]: ...


@dataclass(frozen=True, slots=True)
class Run:
    run_id: str
    project_id: str
    state: str

    def __post_init__(self) -> None:
        _uuid(self.run_id)
        _bounded(self.project_id, "project_id")
        if self.state not in _STATES:
            raise SdkValidationError("run state is invalid")


class NexusClient:
    def __init__(self, transport: HttpTransport) -> None:
        self._transport = transport

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
        request_id: str | None = None,
    ) -> tuple[int, Mapping[str, Any] | list[Any], Mapping[str, str]]:
        if method not in {"GET", "POST"} or not path.startswith("/v1/") or ".." in path:
            raise SdkValidationError("request target is invalid")
        identifier = request_id or str(uuid.uuid4())
        _bounded(identifier, "request_id")
        headers = {"Accept": "application/json", "X-Request-Id": identifier}
        if method == "POST":
            if idempotency_key is None or _KEY.fullmatch(idempotency_key) is None:
                raise SdkValidationError("idempotency key is invalid")
            headers["Idempotency-Key"] = idempotency_key
        elif idempotency_key is not None:
            raise SdkValidationError("idempotency key is valid only for mutations")
        try:
            status, response, response_headers = await self._transport.send(
                method, path, headers, body
            )
        except Exception as exc:
            raise ApiError(
                0, "transport_error", "Control transport failed", identifier, True
            ) from exc
        if not isinstance(status, int) or not isinstance(response, (Mapping, list)):
            raise SdkValidationError("control response is invalid")
        trace = response_headers.get("X-Trace-Id")
        if trace is not None and (not isinstance(trace, str) or _TRACE.fullmatch(trace) is None):
            raise SdkValidationError("control trace is invalid")
        if status >= 400:
            raise _api_error(status, response, identifier)
        if not 200 <= status < 300:
            raise SdkValidationError("control status is invalid")
        return status, response, dict(response_headers)

    async def create_run(
        self, project_id: str, *, idempotency_key: str, request_id: str | None = None
    ) -> Run:
        _bounded(project_id, "project_id")
        _, body, _ = await self.request(
            "POST",
            "/v1/runs",
            body={"project_id": project_id},
            idempotency_key=idempotency_key,
            request_id=request_id,
        )
        return _run(body)

    async def get_run(self, run_id: str, *, request_id: str | None = None) -> Run:
        identifier = _uuid(run_id)
        _, body, _ = await self.request("GET", f"/v1/runs/{identifier}", request_id=request_id)
        return _run(body)

    async def cancel_run(
        self, run_id: str, *, idempotency_key: str, request_id: str | None = None
    ) -> Run:
        return await self._run_mutation(run_id, "cancel", idempotency_key, request_id)

    async def resume_run(
        self, run_id: str, *, idempotency_key: str, request_id: str | None = None
    ) -> Run:
        return await self._run_mutation(run_id, "resume", idempotency_key, request_id)

    async def _run_mutation(
        self, run_id: str, action: str, key: str, request_id: str | None
    ) -> Run:
        identifier = _uuid(run_id)
        _, body, _ = await self.request(
            "POST",
            f"/v1/runs/{identifier}/{action}",
            idempotency_key=key,
            request_id=request_id,
        )
        return _run(body)

    async def list_providers(self, *, request_id: str | None = None) -> tuple[dict[str, Any], ...]:
        return await self._list("/v1/providers", request_id)

    async def list_capabilities(
        self, *, request_id: str | None = None
    ) -> tuple[dict[str, Any], ...]:
        return await self._list("/v1/capabilities", request_id)

    async def list_evidence(
        self, run_id: str, *, request_id: str | None = None
    ) -> tuple[dict[str, Any], ...]:
        identifier = _uuid(run_id)
        return await self._list(f"/v1/runs/{identifier}/evidence", request_id)

    async def _list(self, path: str, request_id: str | None) -> tuple[dict[str, Any], ...]:
        _, body, _ = await self.request("GET", path, request_id=request_id)
        if not isinstance(body, list) or any(not isinstance(item, dict) for item in body):
            raise SdkValidationError("collection response is invalid")
        return tuple(dict(item) for item in body)


def _run(value: object) -> Run:
    if not isinstance(value, Mapping) or set(value) != {"run_id", "project_id", "state"}:
        raise SdkValidationError("run response is invalid")
    try:
        return Run(str(value["run_id"]), str(value["project_id"]), str(value["state"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise SdkValidationError("run response is invalid") from exc


def _api_error(status: int, value: object, fallback_request_id: str) -> ApiError:
    if isinstance(value, Mapping):
        code, message = value.get("code"), value.get("message")
        request_id, retryable = value.get("request_id", fallback_request_id), value.get("retryable")
        if (
            isinstance(code, str)
            and isinstance(message, str)
            and isinstance(request_id, str)
            and isinstance(retryable, bool)
            and len(code) <= 128
            and len(message) <= 2000
        ):
            return ApiError(status, code, message, request_id, retryable)
    return ApiError(status, "api_error", "Control request failed", fallback_request_id, False)


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise SdkValidationError("identifier is invalid")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise SdkValidationError("identifier is invalid") from exc


def _bounded(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise SdkValidationError(f"{name} is invalid")
    return value
