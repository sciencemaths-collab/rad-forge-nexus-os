"""Transport-neutral MCP JSON-RPC gateway over the trusted tool executor."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from nexus_os.domain import TraceId
from nexus_os.tools import ToolError, ToolExecutor, ToolRegistry

_MAX_REQUEST_BYTES = 1024 * 1024
_SCOPES = frozenset({"tools:read", "tools:call"})


@dataclass(frozen=True, slots=True)
class GatewayContext:
    actor_id: str
    project_id: str
    trace_id: TraceId
    scopes: frozenset[str]

    def __post_init__(self) -> None:
        for value, name in ((self.actor_id, "actor_id"), (self.project_id, "project_id")):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{name} is invalid")
        if not isinstance(self.trace_id, TraceId):
            raise ValueError("trace_id is invalid")
        if not isinstance(self.scopes, frozenset) or not self.scopes <= _SCOPES:
            raise ValueError("gateway scopes are invalid")


@dataclass(frozen=True, slots=True)
class GatewayAuditRecord:
    request_id: str
    actor_id: str
    project_id: str
    trace_id: str
    method: str
    tool_name: str | None
    outcome: str
    action_digest: str | None = None


class AuditSink(Protocol):
    def record(self, item: GatewayAuditRecord) -> None: ...


class MemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[GatewayAuditRecord] = []

    def record(self, item: GatewayAuditRecord) -> None:
        self.records.append(item)


class McpGateway:
    def __init__(
        self,
        registry: ToolRegistry,
        executor: ToolExecutor,
        audit: AuditSink,
        *,
        max_calls_per_actor: int = 1000,
    ) -> None:
        if (
            not isinstance(max_calls_per_actor, int)
            or isinstance(max_calls_per_actor, bool)
            or not 1 <= max_calls_per_actor <= 1_000_000
        ):
            raise ValueError("max_calls_per_actor is invalid")
        self._registry = registry
        self._executor = executor
        self._audit = audit
        self._limit = max_calls_per_actor
        self._counts: dict[str, int] = {}

    async def handle(
        self, request: Mapping[str, Any], context: GatewayContext
    ) -> dict[str, Any]:
        request_id: str | int | None = None
        try:
            request_id, method, params = self._request(request)
        except ValueError:
            return self._error(None, -32600, "Invalid Request")

        count = self._counts.get(context.actor_id, 0) + 1
        self._counts[context.actor_id] = count
        if count > self._limit:
            self._audit_item(context, request_id, method, None, "rate_limited")
            return self._error(request_id, -32002, "Rate limit exceeded")

        if method == "tools/list":
            if "tools:read" not in context.scopes:
                return self._unauthorized(context, request_id, method)
            if params != {}:
                return self._invalid_params(context, request_id, method)
            tools = [self._descriptor(item) for item in self._registry.descriptors()]
            self._audit_item(context, request_id, method, None, "allowed")
            return self._success(request_id, {"tools": tools})

        if method == "tools/call":
            if "tools:call" not in context.scopes:
                return self._unauthorized(context, request_id, method)
            if set(params) != {"name", "arguments"}:
                return self._invalid_params(context, request_id, method)
            name, arguments = params.get("name"), params.get("arguments")
            if not isinstance(name, str) or not isinstance(arguments, Mapping):
                return self._invalid_params(context, request_id, method)
            try:
                result = await self._executor.execute(
                    name,
                    arguments,
                    actor_id=context.actor_id,
                    project_id=context.project_id,
                )
            except ToolError:
                self._audit_item(context, request_id, method, name, "rejected")
                return self._error(request_id, -32000, "Tool execution rejected")
            self._audit_item(
                context, request_id, method, name, "allowed", result.action_digest
            )
            return self._success(
                request_id,
                {
                    "content": dict(result.output),
                    "isError": False,
                    "trace_id": str(context.trace_id),
                    "replayed": result.replayed,
                    "action_digest": result.action_digest,
                },
            )

        self._audit_item(context, request_id, method, None, "unknown_method")
        return self._error(request_id, -32601, "Method not found")

    @staticmethod
    def _request(request: Mapping[str, Any]) -> tuple[str | int, str, dict[str, Any]]:
        if not isinstance(request, Mapping):
            raise ValueError("request must be an object")
        try:
            size = len(json.dumps(request, allow_nan=False).encode())
        except (TypeError, ValueError) as exc:
            raise ValueError("request is not JSON") from exc
        if size > _MAX_REQUEST_BYTES or set(request) != {"jsonrpc", "id", "method", "params"}:
            raise ValueError("request envelope is invalid")
        request_id = request.get("id")
        if isinstance(request_id, bool) or not isinstance(request_id, (str, int)):
            raise ValueError("request id is invalid")
        if isinstance(request_id, str) and (not request_id or len(request_id) > 256):
            raise ValueError("request id is invalid")
        method, params = request.get("method"), request.get("params")
        if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
            raise ValueError("request envelope is invalid")
        if not isinstance(params, dict):
            raise ValueError("request params are invalid")
        return request_id, method, params

    @staticmethod
    def _descriptor(item: Any) -> dict[str, Any]:
        return {
            "name": item.name,
            "description": item.description,
            "inputSchema": dict(item.input_schema),
            "outputSchema": dict(item.output_schema),
            "effect": item.effect.value,
            "timeout_seconds": item.timeout_seconds,
            "idempotent": item.idempotent,
            "approval_required": item.approval_required,
        }

    def _unauthorized(
        self, context: GatewayContext, request_id: str | int, method: str
    ) -> dict[str, Any]:
        self._audit_item(context, request_id, method, None, "unauthorized")
        return self._error(request_id, -32001, "Unauthorized")

    def _invalid_params(
        self, context: GatewayContext, request_id: str | int, method: str
    ) -> dict[str, Any]:
        self._audit_item(context, request_id, method, None, "invalid_params")
        return self._error(request_id, -32602, "Invalid params")

    def _audit_item(
        self,
        context: GatewayContext,
        request_id: str | int,
        method: str,
        tool_name: str | None,
        outcome: str,
        action_digest: str | None = None,
    ) -> None:
        self._audit.record(
            GatewayAuditRecord(
                str(request_id),
                context.actor_id,
                context.project_id,
                str(context.trace_id),
                method,
                tool_name,
                outcome,
                action_digest,
            )
        )

    @staticmethod
    def _success(request_id: str | int, result: Mapping[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": dict(result)}

    @staticmethod
    def _error(request_id: str | int | None, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
