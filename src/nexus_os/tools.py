"""Typed deterministic tool registry and policy-gated execution boundary."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from nexus_os.domain import ActionEffect
from nexus_os.policy import (
    ActionRequest,
    DataClass,
    Environment,
    PolicyDecisionKind,
    PolicyEngine,
)
from nexus_os.secrets import redact

_NAME = re.compile(r"^[a-z][a-z0-9_.-]{1,127}$")
_MAX_PAYLOAD_BYTES = 1024 * 1024
ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class ToolError(ValueError):
    """Safe tool-boundary rejection."""


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    name: str
    description: str
    effect: ActionEffect
    timeout_seconds: float
    idempotent: bool
    approval_required: bool
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _NAME.fullmatch(self.name):
            raise ToolError("tool name is invalid")
        if not isinstance(self.description, str) or not 1 <= len(self.description) <= 1024:
            raise ToolError("tool description is invalid")
        if not isinstance(self.effect, ActionEffect):
            raise ToolError("tool effect is invalid")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or not 0 < self.timeout_seconds <= 86_400
        ):
            raise ToolError("tool timeout is invalid")
        if not isinstance(self.idempotent, bool) or not isinstance(
            self.approval_required, bool
        ):
            raise ToolError("tool flags must be boolean")
        input_schema = _schema(self.input_schema)
        output_schema = _schema(self.output_schema)
        object.__setattr__(self, "input_schema", MappingProxyType(input_schema))
        object.__setattr__(self, "output_schema", MappingProxyType(output_schema))


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_name: str
    output: Mapping[str, Any]
    action_digest: str
    replayed: bool


class ToolRegistry:
    def __init__(self) -> None:
        self._descriptors: dict[str, ToolDescriptor] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, descriptor: ToolDescriptor) -> None:
        if descriptor.name in self._descriptors:
            raise ToolError("tool is already registered")
        self._descriptors[descriptor.name] = descriptor

    def bind(self, name: str, handler: ToolHandler) -> None:
        self.get(name)
        if name in self._handlers:
            raise ToolError("tool handler is already bound")
        if not callable(handler):
            raise ToolError("tool handler must be callable")
        self._handlers[name] = handler

    def get(self, name: str) -> ToolDescriptor:
        try:
            return self._descriptors[name]
        except KeyError as exc:
            raise ToolError("tool is not registered") from exc

    def handler(self, name: str) -> ToolHandler:
        try:
            return self._handlers[name]
        except KeyError as exc:
            raise ToolError("tool handler is not bound") from exc

    def descriptors(self) -> tuple[ToolDescriptor, ...]:
        return tuple(self._descriptors[name] for name in sorted(self._descriptors))

    @classmethod
    def from_contract(cls, contract: Mapping[str, Any]) -> ToolRegistry:
        if contract.get("contract_version") != "1.0" or not isinstance(
            contract.get("tools"), list
        ):
            raise ToolError("tool contract is invalid")
        registry = cls()
        for raw in contract["tools"]:
            if not isinstance(raw, Mapping):
                raise ToolError("tool contract entry is invalid")
            try:
                descriptor = ToolDescriptor(
                    name=raw["name"],
                    description=raw["description"],
                    effect=ActionEffect(raw["effect"]),
                    timeout_seconds=raw["timeout_seconds"],
                    idempotent=raw["idempotent"],
                    approval_required=raw["approval_required"],
                    input_schema=raw["inputSchema"],
                    output_schema=raw["outputSchema"],
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ToolError("tool contract entry is invalid") from exc
            registry.register(descriptor)
        return registry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, policy: PolicyEngine) -> None:
        self._registry = registry
        self._policy = policy
        self._cache: dict[tuple[str, str, str], tuple[str, ToolResult]] = {}

    async def execute(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        actor_id: str,
        project_id: str,
    ) -> ToolResult:
        descriptor = self._registry.get(name)
        safe_input, input_digest = _payload(payload)
        _validate(descriptor.input_schema, safe_input, "input")
        decision = self._policy.evaluate(
            ActionRequest(
                actor_id=actor_id,
                project_id=project_id,
                operation=descriptor.name,
                effect=descriptor.effect,
                environment=Environment.LOCAL,
                data_class=DataClass.INTERNAL,
                estimated_cost=0.0,
            )
        )
        if decision.kind is PolicyDecisionKind.DENY:
            raise ToolError("tool execution denied by policy")
        if descriptor.approval_required or decision.kind is PolicyDecisionKind.REQUIRE_APPROVAL:
            raise ToolError("tool execution requires approval")

        cache_key = self._cache_key(descriptor, safe_input, input_digest, project_id)
        if cache_key is not None and cache_key in self._cache:
            prior_digest, prior = self._cache[cache_key]
            if prior_digest != input_digest:
                raise ToolError("idempotency key was reused with different input")
            return ToolResult(prior.tool_name, prior.output, prior.action_digest, True)

        try:
            raw_output = await asyncio.wait_for(
                self._registry.handler(name)(safe_input), timeout=descriptor.timeout_seconds
            )
        except TimeoutError as exc:
            raise ToolError("tool execution timed out") from exc
        except Exception as exc:
            raise ToolError("tool handler failed") from exc
        safe_output, _ = _payload(raw_output)
        _validate(descriptor.output_schema, safe_output, "output")
        result = ToolResult(
            descriptor.name,
            MappingProxyType(safe_output),
            decision.action_digest,
            False,
        )
        if cache_key is not None:
            self._cache[cache_key] = (input_digest, result)
        return result

    @staticmethod
    def _cache_key(
        descriptor: ToolDescriptor,
        payload: dict[str, Any],
        input_digest: str,
        project_id: str,
    ) -> tuple[str, str, str] | None:
        if not descriptor.idempotent:
            return None
        properties = descriptor.input_schema.get("properties", {})
        if not isinstance(properties, Mapping) or "idempotency_key" not in properties:
            return (project_id, descriptor.name, input_digest)
        value = payload.get("idempotency_key")
        if not isinstance(value, str) or not 16 <= len(value) <= 256:
            raise ToolError("idempotent tool requires a bounded idempotency_key")
        return (project_id, descriptor.name, value)


def _schema(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        encoded = json.dumps(value, sort_keys=True, allow_nan=False)
        decoded = json.loads(encoded)
        Draft202012Validator.check_schema(decoded)
    except (TypeError, ValueError, SchemaError) as exc:
        raise ToolError("tool JSON schema is invalid") from exc
    if not isinstance(decoded, dict) or len(encoded.encode()) > 256 * 1024:
        raise ToolError("tool JSON schema is invalid or oversized")
    return decoded


def _payload(value: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    if not isinstance(value, Mapping):
        raise ToolError("tool payload must be an object")
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ToolError("tool payload must contain canonical JSON") from exc
    if len(encoded.encode()) > _MAX_PAYLOAD_BYTES or not isinstance(decoded, dict):
        raise ToolError("tool payload is oversized or invalid")
    safe = redact(decoded)
    if not isinstance(safe, dict):  # pragma: no cover - decoded is an object
        raise ToolError("tool payload is invalid")
    digest = f"sha256:{hashlib.sha256(encoded.encode()).hexdigest()}"
    return safe, digest


def _validate(schema: Mapping[str, Any], value: dict[str, Any], boundary: str) -> None:
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
    except ValidationError as exc:
        raise ToolError(f"tool {boundary} validation failed") from exc
