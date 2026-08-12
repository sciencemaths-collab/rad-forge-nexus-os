"""Provider-neutral, immutable domain values for the NEXUS kernel.

This module defines data and validation only. Lifecycle transition rules belong
to the state-machine component; persistence and provider behavior belong behind
their respective ports.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Self
from uuid import UUID, uuid4

SCHEMA_VERSION = "1.0"
_TASK_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_ARTIFACT_URI_PATTERN = re.compile(r"^artifact://[A-Za-z0-9._~!$&'()*+,;=:@/-]+$")


class DomainValidationError(ValueError):
    """A stable, safe failure raised for invalid domain input."""


@dataclass(frozen=True, slots=True)
class RunId:
    """Type-safe run UUID."""

    value: UUID

    @classmethod
    def new(cls) -> Self:
        return cls(uuid4())

    @classmethod
    def parse(cls, value: object) -> Self:
        try:
            parsed = value if isinstance(value, UUID) else UUID(str(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise DomainValidationError("run_id must be a UUID") from exc
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class TaskId:
    """Validated task identifier shared by graph and runtime contracts."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _TASK_ID_PATTERN.fullmatch(self.value):
            raise DomainValidationError("task_id must match ^[a-z][a-z0-9_-]{1,63}$")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TraceId:
    """W3C-compatible 16-byte trace identifier encoded as lowercase hex."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not _TRACE_ID_PATTERN.fullmatch(self.value):
            raise DomainValidationError("trace_id must be 32 lowercase hexadecimal characters")
        if self.value == "0" * 32:
            raise DomainValidationError("trace_id must not be all zeroes")

    def __str__(self) -> str:
        return self.value


class ActionEffect(StrEnum):
    READ_ONLY = "READ_ONLY"
    WORKSPACE_WRITE = "WORKSPACE_WRITE"
    SENSITIVE = "SENSITIVE"
    DESTRUCTIVE = "DESTRUCTIVE"


class FailureClass(StrEnum):
    IMPLEMENTATION_BUG = "IMPLEMENTATION_BUG"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    ENVIRONMENT = "ENVIRONMENT"
    PROVIDER = "PROVIDER"
    SECURITY_POLICY = "SECURITY_POLICY"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class RunState(StrEnum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLING = "CANCELLING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED, self.CANCELLED}


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"

    @property
    def is_terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED, self.CANCELLED, self.SKIPPED}


class TaskEventKind(StrEnum):
    ACCEPTED = "ACCEPTED"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    ARTIFACT = "ARTIFACT"
    LOG = "LOG"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RuntimeCommandKind(StrEnum):
    START_RUN = "START_RUN"
    CANCEL_RUN = "CANCEL_RUN"
    RESUME_RUN = "RESUME_RUN"


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    """Canonical task instruction emitted by the graph compiler."""

    task_id: TaskId
    kind: str
    depends_on: tuple[TaskId, ...]
    effect: ActionEffect
    timeout_seconds: int
    max_attempts: int
    backoff_seconds: float
    input: Mapping[str, Any]
    acceptance_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_token(self.kind, "kind")
        if not isinstance(self.timeout_seconds, int) or not 1 <= self.timeout_seconds <= 86_400:
            raise DomainValidationError("timeout_seconds must be an integer from 1 to 86400")
        if not isinstance(self.max_attempts, int) or not 1 <= self.max_attempts <= 20:
            raise DomainValidationError("max_attempts must be an integer from 1 to 20")
        if (
            isinstance(self.backoff_seconds, bool)
            or not isinstance(self.backoff_seconds, (int, float))
            or not math.isfinite(self.backoff_seconds)
            or not 0 <= self.backoff_seconds <= 3600
        ):
            raise DomainValidationError("backoff_seconds must be finite and from 0 to 3600")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise DomainValidationError("depends_on must not contain duplicates")
        if self.task_id in self.depends_on:
            raise DomainValidationError("task cannot depend on itself")
        if len(set(self.acceptance_ids)) != len(self.acceptance_ids):
            raise DomainValidationError("acceptance_ids must not contain duplicates")
        for acceptance_id in self.acceptance_ids:
            _require_nonempty(acceptance_id, "acceptance_ids")
        object.__setattr__(self, "depends_on", tuple(self.depends_on))
        object.__setattr__(self, "acceptance_ids", tuple(self.acceptance_ids))
        object.__setattr__(self, "input", _freeze_object(self.input, "input"))

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "task_id": str(self.task_id),
            "kind": self.kind,
            "depends_on": sorted(str(item) for item in self.depends_on),
            "effect": self.effect.value,
            "timeout_seconds": self.timeout_seconds,
            "retry": {
                "max_attempts": self.max_attempts,
                "backoff_seconds": self.backoff_seconds,
            },
            "input": _thaw_json(self.input),
            "acceptance_ids": sorted(self.acceptance_ids),
        }


@dataclass(frozen=True, slots=True)
class TaskGraph:
    """Validated DAG whose digest is independent of caller task ordering."""

    graph_id: UUID
    project_id: str
    tasks: tuple[TaskDefinition, ...]
    schema_version: str = SCHEMA_VERSION
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.graph_id, UUID):
            raise DomainValidationError("graph_id must be a UUID")
        _require_nonempty(self.project_id, "project_id")
        if self.schema_version != SCHEMA_VERSION:
            raise DomainValidationError(f"schema_version must be {SCHEMA_VERSION}")
        tasks = tuple(self.tasks)
        if not tasks:
            raise DomainValidationError("tasks must contain at least one task")
        identifiers = [task.task_id for task in tasks]
        if len(set(identifiers)) != len(identifiers):
            raise DomainValidationError("duplicate task_id in graph")
        object.__setattr__(self, "tasks", tasks)
        canonical = json.dumps(
            self.canonical_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        object.__setattr__(self, "digest", f"sha256:{digest}")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "graph_id": str(self.graph_id),
            "project_id": self.project_id,
            "tasks": [
                task.canonical_dict()
                for task in sorted(self.tasks, key=lambda item: str(item.task_id))
            ],
        }


@dataclass(frozen=True, slots=True)
class Failure:
    classification: FailureClass
    code: str
    message: str
    retryable: bool
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_token(self.code, "code")
        _require_nonempty(self.message, "message")
        non_retryable = {FailureClass.SECURITY_POLICY, FailureClass.CANCELLED}
        if self.classification in non_retryable and self.retryable:
            raise DomainValidationError(f"{self.classification.value} must not be retryable")
        object.__setattr__(self, "details", _freeze_object(self.details, "details"))


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_id: str
    uri: str
    digest: str
    media_type: str
    size_bytes: int

    def __post_init__(self) -> None:
        _require_token(self.artifact_id, "artifact_id")
        if not isinstance(self.uri, str) or not _ARTIFACT_URI_PATTERN.fullmatch(self.uri):
            raise DomainValidationError("artifact URI must use the artifact:// scheme")
        if not isinstance(self.digest, str) or not _DIGEST_PATTERN.fullmatch(self.digest):
            raise DomainValidationError("digest must be a sha256 content digest")
        _require_nonempty(self.media_type, "media_type")
        invalid_size = (
            not isinstance(self.size_bytes, int)
            or isinstance(self.size_bytes, bool)
            or self.size_bytes < 0
        )
        if invalid_size:
            raise DomainValidationError("size_bytes must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: TaskId
    status: TaskStatus
    artifacts: tuple[ArtifactRef, ...] = ()
    output: Mapping[str, Any] = field(default_factory=dict)
    failure: Failure | None = None

    def __post_init__(self) -> None:
        if not self.status.is_terminal:
            raise DomainValidationError("task result status must be terminal")
        if self.status is TaskStatus.FAILED and self.failure is None:
            raise DomainValidationError("failed task result requires a failure")
        if self.status is not TaskStatus.FAILED and self.failure is not None:
            raise DomainValidationError("non-failed task result cannot carry a failure")
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "output", _freeze_object(self.output, "output"))


@dataclass(frozen=True, slots=True)
class TaskEvent:
    task_id: TaskId
    sequence: int
    occurred_at: datetime
    kind: TaskEventKind
    trace_id: TraceId
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        invalid_sequence = (
            not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence < 1
        )
        if invalid_sequence:
            raise DomainValidationError("sequence must be a positive integer")
        utc_offset = UTC.utcoffset(self.occurred_at)
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() != utc_offset:
            raise DomainValidationError("occurred_at must be timezone-aware UTC")
        object.__setattr__(self, "payload", _freeze_object(self.payload, "payload"))


@dataclass(frozen=True, slots=True)
class RuntimeCommand:
    """Normalized mutating command accepted by future application services."""

    command_id: UUID
    run_id: RunId
    kind: RuntimeCommandKind
    issued_at: datetime
    trace_id: TraceId
    idempotency_key: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.command_id, UUID):
            raise DomainValidationError("command_id must be a UUID")
        if self.issued_at.tzinfo is None or self.issued_at.utcoffset() != UTC.utcoffset(
            self.issued_at
        ):
            raise DomainValidationError("issued_at must be timezone-aware UTC")
        _require_nonempty(self.idempotency_key, "idempotency_key")
        if len(self.idempotency_key) > 256:
            raise DomainValidationError("idempotency_key must not exceed 256 characters")
        object.__setattr__(self, "payload", _freeze_object(self.payload, "payload"))


def _require_nonempty(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field_name} must be a non-empty string")


def _require_token(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not _TOKEN_PATTERN.fullmatch(value):
        raise DomainValidationError(f"{field_name} must be a lowercase canonical token")


def _freeze_object(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainValidationError(f"{field_name} must be a JSON object")
    frozen = _freeze_json(value, field_name)
    if not isinstance(frozen, MappingProxyType):  # pragma: no cover - defensive invariant
        raise DomainValidationError(f"{field_name} must be a JSON object")
    return frozen


def _freeze_json(value: object, path: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainValidationError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DomainValidationError(f"{path} contains a non-string object key")
            result[key] = _freeze_json(item, f"{path}.{key}")
        return MappingProxyType(result)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_json(item, f"{path}[]") for item in value)
    raise DomainValidationError(f"{path} contains a value that is not JSON-compatible")


def _thaw_json(value: object) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value

