"""Deterministic, provider-neutral action policy evaluation."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from nexus_os.domain import ActionEffect

_OPERATION_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_MAX_METADATA_BYTES = 32 * 1024


class PolicyValidationError(ValueError):
    """Safe rejection of an invalid policy input or rule set."""


class Environment(StrEnum):
    LOCAL = "LOCAL"
    TEST = "TEST"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


class DataClass(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class PolicyDecisionKind(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True, slots=True)
class ActionRequest:
    """Trusted structured action attributes evaluated independently of task prose."""

    actor_id: str
    project_id: str
    operation: str
    effect: ActionEffect
    environment: Environment
    data_class: DataClass
    estimated_cost: float
    external_communication: bool = False
    publishing: bool = False
    security_weakening: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _nonempty(self.actor_id, "actor_id")
        _nonempty(self.project_id, "project_id")
        if not isinstance(self.operation, str) or not _OPERATION_PATTERN.fullmatch(self.operation):
            raise PolicyValidationError("operation must be a lowercase canonical token")
        if not isinstance(self.effect, ActionEffect):
            raise PolicyValidationError("effect must be an ActionEffect")
        if not isinstance(self.environment, Environment):
            raise PolicyValidationError("environment must be an Environment")
        if not isinstance(self.data_class, DataClass):
            raise PolicyValidationError("data_class must be a DataClass")
        if (
            isinstance(self.estimated_cost, bool)
            or not isinstance(self.estimated_cost, (int, float))
            or not math.isfinite(self.estimated_cost)
            or self.estimated_cost < 0
        ):
            raise PolicyValidationError("estimated cost must be finite and non-negative")
        for name in ("external_communication", "publishing", "security_weakening"):
            if not isinstance(getattr(self, name), bool):
                raise PolicyValidationError(f"{name} must be a boolean")
        metadata = _canonical_metadata(self.metadata)
        object.__setattr__(self, "metadata", MappingProxyType(metadata))

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "project_id": self.project_id,
            "operation": self.operation,
            "effect": self.effect.value,
            "environment": self.environment.value,
            "data_class": self.data_class.value,
            "estimated_cost": self.estimated_cost,
            "external_communication": self.external_communication,
            "publishing": self.publishing,
            "security_weakening": self.security_weakening,
            "metadata": dict(self.metadata),
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class PolicyRules:
    allowed_operations: frozenset[str] | None = None
    denied_operations: frozenset[str] = frozenset()
    approval_effects: frozenset[ActionEffect] = frozenset(
        {ActionEffect.SENSITIVE, ActionEffect.DESTRUCTIVE}
    )

    def __post_init__(self) -> None:
        operation_sets = [self.denied_operations]
        if self.allowed_operations is not None:
            operation_sets.append(self.allowed_operations)
        for operations in operation_sets:
            for operation in operations:
                if not isinstance(operation, str) or not _OPERATION_PATTERN.fullmatch(operation):
                    raise PolicyValidationError("policy operation must be canonical")
        if self.allowed_operations is not None and (
            self.allowed_operations & self.denied_operations
        ):
            raise PolicyValidationError("an operation cannot be both allowed and denied")
        if not all(isinstance(effect, ActionEffect) for effect in self.approval_effects):
            raise PolicyValidationError("approval_effects must contain ActionEffect values")


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    kind: PolicyDecisionKind
    action_digest: str
    reason_codes: tuple[str, ...]


class PolicyEngine:
    """Evaluate structured action facts with denial precedence."""

    def __init__(self, rules: PolicyRules) -> None:
        self._rules = rules

    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        deny: set[str] = set()
        approval: set[str] = set()

        if request.operation in self._rules.denied_operations:
            deny.add("operation.denied")
        if (
            self._rules.allowed_operations is not None
            and request.operation not in self._rules.allowed_operations
        ):
            deny.add("operation.not_allowed")
        if request.security_weakening:
            deny.add("security.weakening")

        if request.effect in self._rules.approval_effects:
            approval.add(f"effect.{request.effect.value.lower()}")
        if request.environment is Environment.PRODUCTION:
            approval.add("environment.production")
        if request.external_communication:
            approval.add("external.communication")
        if request.publishing:
            approval.add("external.publishing")
        if request.estimated_cost > 0:
            approval.add("cost.spending")
        if request.data_class is DataClass.RESTRICTED:
            approval.add("data.restricted")

        if deny:
            return PolicyDecision(PolicyDecisionKind.DENY, request.digest, tuple(sorted(deny)))
        if approval:
            return PolicyDecision(
                PolicyDecisionKind.REQUIRE_APPROVAL,
                request.digest,
                tuple(sorted(approval)),
            )
        return PolicyDecision(PolicyDecisionKind.ALLOW, request.digest, ("policy.allowed",))


def _nonempty(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise PolicyValidationError(f"{field_name} must be a non-empty bounded string")


def _canonical_metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PolicyValidationError("metadata must be a JSON object")
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise PolicyValidationError("metadata must contain canonical JSON values") from exc
    if len(encoded.encode()) > _MAX_METADATA_BYTES:
        raise PolicyValidationError("metadata exceeds 32 KiB")
    if not isinstance(decoded, dict):  # pragma: no cover - mapping guarantees object
        raise PolicyValidationError("metadata must be a JSON object")
    return decoded
