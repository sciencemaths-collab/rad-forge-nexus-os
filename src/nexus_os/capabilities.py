"""Versioned, fail-closed capability registration, discovery, and routing."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from nexus_os.domain import ActionEffect
from nexus_os.qualification import CapabilityQualification, CapabilityState
from nexus_os.tools import ToolDescriptor

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")


class CapabilityError(ValueError):
    """Safe capability protocol rejection."""


class CapabilityKind(StrEnum):
    NATIVE_TOOL = "NATIVE_TOOL"
    ENGINE_OPERATION = "ENGINE_OPERATION"
    CONNECTOR = "CONNECTOR"
    HARDWARE_BACKEND = "HARDWARE_BACKEND"
    DOMAIN_PACK = "DOMAIN_PACK"


class NetworkAccess(StrEnum):
    DENIED = "DENIED"
    POLICY_SCOPED = "POLICY_SCOPED"


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    timeout_seconds: float
    memory_mib: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or not 0 < self.timeout_seconds <= 86_400
        ):
            raise CapabilityError("capability timeout is invalid")
        if (
            isinstance(self.memory_mib, bool)
            or not isinstance(self.memory_mib, int)
            or not 1 <= self.memory_mib <= 1_048_576
        ):
            raise CapabilityError("capability memory limit is invalid")


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    capability_id: str
    version: str
    kind: CapabilityKind
    description: str
    operations: tuple[str, ...]
    effects: frozenset[ActionEffect]
    deterministic: bool
    network_access: NetworkAccess
    approval_required: bool
    qualification_required: bool
    resource_limits: ResourceLimits
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise CapabilityError("capability schema version is unsupported")
        if not isinstance(self.capability_id, str) or not _IDENTIFIER.fullmatch(self.capability_id):
            raise CapabilityError("capability_id is invalid")
        if not isinstance(self.version, str) or not _VERSION.fullmatch(self.version):
            raise CapabilityError("capability version is invalid")
        if not isinstance(self.kind, CapabilityKind):
            raise CapabilityError("capability kind is invalid")
        if not isinstance(self.description, str) or not 1 <= len(self.description) <= 1024:
            raise CapabilityError("capability description is invalid")
        if (
            not self.operations
            or len(set(self.operations)) != len(self.operations)
            or any(
                not isinstance(item, str) or not _IDENTIFIER.fullmatch(item)
                for item in self.operations
            )
        ):
            raise CapabilityError("capability operations are invalid")
        if not self.effects or any(not isinstance(item, ActionEffect) for item in self.effects):
            raise CapabilityError("capability effects are invalid")
        if not all(
            isinstance(item, bool)
            for item in (self.deterministic, self.approval_required, self.qualification_required)
        ):
            raise CapabilityError("capability flags must be boolean")
        if not isinstance(self.network_access, NetworkAccess) or not isinstance(
            self.resource_limits, ResourceLimits
        ):
            raise CapabilityError("capability execution constraints are invalid")

    def canonical(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "capability_id": self.capability_id,
            "version": self.version,
            "kind": self.kind.value,
            "description": self.description,
            "operations": sorted(self.operations),
            "effects": sorted(item.value for item in self.effects),
            "deterministic": self.deterministic,
            "network_access": self.network_access.value,
            "approval_required": self.approval_required,
            "qualification_required": self.qualification_required,
            "resource_limits": {
                "timeout_seconds": self.resource_limits.timeout_seconds,
                "memory_mib": self.resource_limits.memory_mib,
            },
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    manifest: CapabilityManifest
    qualification: CapabilityQualification | None
    implementation: object


@dataclass(frozen=True, slots=True)
class CapabilityDiscovery:
    manifest: Mapping[str, Any]
    manifest_digest: str
    qualification_state: CapabilityState
    qualification_expires_at: datetime | None
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RouteRequest:
    capability_id: str
    operation: str
    allowed_effects: frozenset[ActionEffect]
    allow_network: bool = False
    version: str | None = None
    max_timeout_seconds: float | None = None
    max_memory_mib: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not _IDENTIFIER.fullmatch(self.capability_id):
            raise CapabilityError("route capability_id is invalid")
        if not isinstance(self.operation, str) or not _IDENTIFIER.fullmatch(self.operation):
            raise CapabilityError("route operation is invalid")
        if self.version is not None and (
            not isinstance(self.version, str) or not _VERSION.fullmatch(self.version)
        ):
            raise CapabilityError("route version is invalid")
        if not isinstance(self.allowed_effects, frozenset) or any(
            not isinstance(item, ActionEffect) for item in self.allowed_effects
        ):
            raise CapabilityError("route effects are invalid")
        if not isinstance(self.allow_network, bool):
            raise CapabilityError("route network scope is invalid")
        if self.max_timeout_seconds is not None and (
            isinstance(self.max_timeout_seconds, bool)
            or not isinstance(self.max_timeout_seconds, (int, float))
            or not math.isfinite(self.max_timeout_seconds)
            or self.max_timeout_seconds <= 0
        ):
            raise CapabilityError("route timeout limit is invalid")
        if self.max_memory_mib is not None and (
            isinstance(self.max_memory_mib, bool)
            or not isinstance(self.max_memory_mib, int)
            or self.max_memory_mib < 1
        ):
            raise CapabilityError("route memory limit is invalid")


class CapabilityRegistry:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], CapabilityRecord] = {}

    def register(
        self,
        manifest: CapabilityManifest,
        implementation: object,
        qualification: CapabilityQualification | None = None,
    ) -> None:
        key = (manifest.capability_id, manifest.version)
        if key in self._records:
            raise CapabilityError("capability version is already registered")
        if implementation is None:
            raise CapabilityError("capability implementation is required")
        if qualification is not None and qualification.capability_id != manifest.capability_id:
            raise CapabilityError("qualification capability does not match manifest")
        self._records[key] = CapabilityRecord(manifest, qualification, implementation)

    def discover(
        self, *, capability_id: str | None = None, operation: str | None = None
    ) -> tuple[CapabilityDiscovery, ...]:
        found = []
        for key in sorted(self._records):
            record = self._records[key]
            if capability_id is not None and record.manifest.capability_id != capability_id:
                continue
            if operation is not None and operation not in record.manifest.operations:
                continue
            qualification = record.qualification
            found.append(
                CapabilityDiscovery(
                    MappingProxyType(record.manifest.canonical()),
                    record.manifest.digest,
                    CapabilityState.UNKNOWN if qualification is None else qualification.state,
                    None if qualification is None else qualification.expires_at,
                    () if qualification is None else qualification.limitations,
                )
            )
        return tuple(found)

    def route(self, request: RouteRequest, *, at: datetime) -> CapabilityRecord:
        if at.tzinfo is None or at.utcoffset() != UTC.utcoffset(at):
            raise CapabilityError("routing time must be timezone-aware UTC")
        eligible = []
        for (capability_id, version), record in self._records.items():
            manifest = record.manifest
            if capability_id != request.capability_id or (
                request.version is not None and version != request.version
            ):
                continue
            if request.operation not in manifest.operations or not manifest.effects.issubset(
                request.allowed_effects
            ):
                continue
            if manifest.network_access is NetworkAccess.POLICY_SCOPED and not request.allow_network:
                continue
            if (
                request.max_timeout_seconds is not None
                and manifest.resource_limits.timeout_seconds > request.max_timeout_seconds
            ):
                continue
            if (
                request.max_memory_mib is not None
                and manifest.resource_limits.memory_mib > request.max_memory_mib
            ):
                continue
            if manifest.qualification_required and not _is_qualified(record.qualification, at):
                continue
            eligible.append(record)
        if not eligible:
            raise CapabilityError("no eligible capability implementation")
        if len(eligible) != 1:
            raise CapabilityError("capability route is ambiguous; pin an exact version")
        return eligible[0]


def manifest_from_tool(
    descriptor: ToolDescriptor,
    *,
    version: str = "1.0.0",
    memory_mib: int = 256,
    qualification_required: bool = True,
) -> CapabilityManifest:
    """Adapt a native governed tool without changing its execution semantics."""
    return CapabilityManifest(
        capability_id=descriptor.name,
        version=version,
        kind=CapabilityKind.NATIVE_TOOL,
        description=descriptor.description,
        operations=(descriptor.name,),
        effects=frozenset({descriptor.effect}),
        deterministic=descriptor.idempotent,
        network_access=NetworkAccess.DENIED,
        approval_required=descriptor.approval_required,
        qualification_required=qualification_required,
        resource_limits=ResourceLimits(descriptor.timeout_seconds, memory_mib),
    )


def _is_qualified(qualification: CapabilityQualification | None, at: datetime) -> bool:
    return (
        qualification is not None
        and qualification.state is CapabilityState.QUALIFIED
        and not qualification.limitations
        and qualification.evaluated_at.tzinfo is not None
        and qualification.evaluated_at.utcoffset() == UTC.utcoffset(qualification.evaluated_at)
        and qualification.evaluated_at <= at
        and (qualification.expires_at is None or qualification.expires_at > at)
    )
