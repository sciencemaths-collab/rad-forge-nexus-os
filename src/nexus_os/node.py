"""Durable, bounded local execution host for qualified RAD capabilities."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
import threading
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from nexus_os.capabilities import (
    CapabilityManifest,
    CapabilityRecord,
    CapabilityRegistry,
    RouteRequest,
)
from nexus_os.qualification import CapabilityQualification
from nexus_os.secrets import redact

_NODE_ID = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_ACTOR_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{1,127}$")
_NODE_SCOPES = frozenset({"node:read", "node:execute", "node:drain"})
_GENESIS = "sha256:" + "0" * 64
_MAX_PAYLOAD = 1024 * 1024


class NodeError(ValueError):
    """Safe RAD Node rejection."""


class NodeState(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    READY = "READY"
    DRAINING = "DRAINING"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True, slots=True)
class NodeSnapshot:
    node_id: str
    state: NodeState
    revision: int
    capabilities: tuple[str, ...]
    active_leases: int
    event_head: str

    def canonical(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "node_id": self.node_id,
            "state": self.state.value,
            "revision": self.revision,
            "capabilities": list(self.capabilities),
            "active_leases": self.active_leases,
            "event_head": self.event_head,
        }


@dataclass(frozen=True, slots=True)
class NodeExecution:
    lease_id: UUID
    capability_id: str
    version: str
    operation: str
    output: Mapping[str, Any]


NodeHandler = Callable[[str, Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


@dataclass(frozen=True, slots=True)
class NodePrincipal:
    actor_id: str
    scopes: frozenset[str]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.actor_id, str)
            or not _ACTOR_ID.fullmatch(self.actor_id)
            or not isinstance(self.scopes, frozenset)
            or not self.scopes <= _NODE_SCOPES
        ):
            raise NodeError("node principal is invalid")


class NodeStore:
    def __init__(self, path: Path, node_id: str) -> None:
        if not isinstance(node_id, str) or not _NODE_ID.fullmatch(node_id):
            raise NodeError("node_id is invalid")
        self._connection = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript("""
        CREATE TABLE IF NOT EXISTS node_metadata (
          slot INTEGER PRIMARY KEY CHECK(slot=1), node_id TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS immutable_node_metadata
          BEFORE UPDATE ON node_metadata BEGIN
            SELECT RAISE(ABORT, 'node identity is immutable');
          END;
        CREATE TRIGGER IF NOT EXISTS no_node_metadata_delete
          BEFORE DELETE ON node_metadata BEGIN
            SELECT RAISE(ABORT, 'node identity is immutable');
          END;
        CREATE TABLE IF NOT EXISTS node_capabilities (
          capability_id TEXT NOT NULL, version TEXT NOT NULL,
          manifest_digest TEXT NOT NULL, manifest_json TEXT NOT NULL,
          PRIMARY KEY(capability_id, version)
        );
        CREATE TRIGGER IF NOT EXISTS immutable_node_capability
          BEFORE UPDATE ON node_capabilities BEGIN
            SELECT RAISE(ABORT, 'node capability is immutable');
          END;
        CREATE TRIGGER IF NOT EXISTS no_node_capability_delete
          BEFORE DELETE ON node_capabilities BEGIN
            SELECT RAISE(ABORT, 'node capability is immutable');
          END;
        CREATE TABLE IF NOT EXISTS node_events (
          sequence INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, kind TEXT NOT NULL,
          payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
          event_hash TEXT NOT NULL UNIQUE
        );
        CREATE TRIGGER IF NOT EXISTS immutable_node_event
          BEFORE UPDATE ON node_events BEGIN
            SELECT RAISE(ABORT, 'node events are immutable');
          END;
        CREATE TRIGGER IF NOT EXISTS no_node_event_delete
          BEFORE DELETE ON node_events BEGIN
            SELECT RAISE(ABORT, 'node events are append only');
          END;
        """)
        row = self._connection.execute("SELECT node_id FROM node_metadata WHERE slot=1").fetchone()
        if row is None:
            self._connection.execute("INSERT INTO node_metadata VALUES (1, ?)", (node_id,))
        elif row[0] != node_id:
            self._connection.close()
            raise NodeError("stored node identity does not match configured node_id")
        self._node_id = node_id
        self._lock = threading.RLock()

    @property
    def node_id(self) -> str:
        return self._node_id

    def bind(self, manifest: CapabilityManifest, *, at: datetime) -> None:
        _utc(at)
        encoded = _canonical(manifest.canonical())
        with self._lock:
            row = self._connection.execute(
                "SELECT manifest_digest FROM node_capabilities WHERE capability_id=? AND version=?",
                (manifest.capability_id, manifest.version),
            ).fetchone()
            if row is not None:
                if row[0] != manifest.digest:
                    raise NodeError("persisted capability manifest digest mismatch")
                return
            self._connection.execute(
                "INSERT INTO node_capabilities VALUES (?, ?, ?, ?)",
                (manifest.capability_id, manifest.version, manifest.digest, encoded.decode()),
            )
            self.append(
                "CAPABILITY_BOUND",
                {
                    "capability_id": manifest.capability_id,
                    "version": manifest.version,
                    "manifest_digest": manifest.digest,
                },
                at,
            )

    def append(self, kind: str, payload: Mapping[str, Any], at: datetime) -> str:
        _utc(at)
        if not isinstance(kind, str) or not re.fullmatch(r"[A-Z][A-Z_]{1,63}", kind):
            raise NodeError("node event kind is invalid")
        safe = json.loads(_canonical(redact(dict(payload))))
        if not isinstance(safe, dict) or len(_canonical(safe)) > _MAX_PAYLOAD:
            raise NodeError("node event payload is invalid")
        with self._lock:
            row = self._connection.execute(
                "SELECT sequence, timestamp, event_hash FROM node_events "
                "ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            sequence, previous = (1, _GENESIS) if row is None else (int(row[0]) + 1, str(row[2]))
            if row is not None and at < datetime.fromisoformat(str(row[1])):
                raise NodeError("node event timestamp precedes durable history")
            body = {
                "sequence": sequence,
                "timestamp": at.isoformat(),
                "kind": kind,
                "payload": safe,
                "previous_hash": previous,
            }
            digest = "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()
            self._connection.execute(
                "INSERT INTO node_events VALUES (?, ?, ?, ?, ?, ?)",
                (sequence, at.isoformat(), kind, _canonical(safe).decode(), previous, digest),
            )
            return digest

    def events(self) -> tuple[dict[str, Any], ...]:
        rows = self._connection.execute("SELECT * FROM node_events ORDER BY sequence").fetchall()
        previous = _GENESIS
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(str(row[3]))
            body = {
                "sequence": int(row[0]),
                "timestamp": str(row[1]),
                "kind": str(row[2]),
                "payload": payload,
                "previous_hash": str(row[4]),
            }
            digest = "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()
            if int(row[0]) != len(result) + 1 or row[4] != previous or row[5] != digest:
                raise NodeError("node event chain failed integrity verification")
            result.append({**body, "event_hash": digest})
            previous = digest
        return tuple(result)

    def capabilities(self) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT capability_id, version, manifest_digest, manifest_json "
            "FROM node_capabilities ORDER BY capability_id, version"
        ).fetchall()
        for row in rows:
            try:
                manifest = json.loads(str(row[3]))
                digest = "sha256:" + hashlib.sha256(_canonical(manifest)).hexdigest()
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise NodeError("stored capability manifest failed integrity validation") from exc
            if (
                not isinstance(manifest, dict)
                or manifest.get("capability_id") != row[0]
                or manifest.get("version") != row[1]
                or digest != row[2]
            ):
                raise NodeError("stored capability manifest failed integrity validation")
        return tuple(f"{row[0]}@{row[1]}" for row in rows)

    def close(self) -> None:
        self._connection.close()


class RadNode:
    def __init__(
        self, store: NodeStore, registry: CapabilityRegistry, *, max_concurrency: int = 4
    ) -> None:
        if (
            not isinstance(max_concurrency, int)
            or isinstance(max_concurrency, bool)
            or not 1 <= max_concurrency <= 1024
        ):
            raise NodeError("max_concurrency must be from 1 to 1024")
        self._store = store
        self._registry = registry
        self._handlers: dict[tuple[str, str], NodeHandler] = {}
        self._state = NodeState.STOPPED
        self._active: set[UUID] = set()
        self._maximum = max_concurrency
        self._lock = asyncio.Lock()

    def bind(
        self,
        manifest: CapabilityManifest,
        implementation: object,
        handler: NodeHandler,
        qualification: CapabilityQualification | None = None,
        *,
        at: datetime,
    ) -> None:
        if not callable(handler):
            raise NodeError("node capability handler is invalid")
        if implementation is None:
            raise NodeError("node capability implementation is required")
        if qualification is not None and qualification.capability_id != manifest.capability_id:
            raise NodeError("qualification capability does not match manifest")
        self._store.bind(manifest, at=at)
        self._registry.register(manifest, implementation, qualification)
        self._handlers[(manifest.capability_id, manifest.version)] = handler

    def start(self, *, at: datetime) -> None:
        if self._state is not NodeState.STOPPED:
            raise NodeError("node can start only from STOPPED")
        prior = self._store.events()
        active = _active_leases(prior)
        for lease_id in sorted(active):
            self._store.append("LEASE_ABANDONED", {"lease_id": lease_id}, at)
        self._transition(NodeState.STARTING, at)
        self._transition(NodeState.READY, at)

    def drain(self, identity: NodePrincipal, *, at: datetime) -> None:
        _scope(identity, "node:drain")
        if self._state is not NodeState.READY:
            raise NodeError("node can drain only from READY")
        self._transition(NodeState.DRAINING, at)
        if not self._active:
            self._transition(NodeState.STOPPED, at)

    def inventory(self, identity: NodePrincipal) -> tuple[Any, ...]:
        _scope(identity, "node:read")
        return self._registry.discover()

    def snapshot(self, identity: NodePrincipal) -> NodeSnapshot:
        _scope(identity, "node:read")
        events = self._store.events()
        head = _GENESIS if not events else str(events[-1]["event_hash"])
        return NodeSnapshot(
            self._store.node_id,
            self._state,
            len(events),
            self._store.capabilities(),
            len(self._active),
            head,
        )

    def health(self) -> str:
        """Return a transport-safe probe derived from verified state."""
        try:
            self._store.events()
            self._store.capabilities()
        except NodeError:
            return "DEGRADED"
        return "HEALTHY" if self._state is NodeState.READY else self._state.value

    async def execute(
        self,
        request: RouteRequest,
        payload: Mapping[str, Any],
        identity: NodePrincipal,
        *,
        at: datetime,
    ) -> NodeExecution:
        _scope(identity, "node:execute")
        _utc(at)
        safe_payload = _safe_payload(payload)
        async with self._lock:
            if self._state is not NodeState.READY:
                raise NodeError("node is not accepting work")
            if len(self._active) >= self._maximum:
                raise NodeError("node concurrency limit reached")
            record = self._registry.route(request, at=at)
            lease_id = uuid4()
            self._active.add(lease_id)
            self._store.append("LEASE_ACQUIRED", _lease_payload(lease_id, record, request), at)
        handler = self._handlers.get((record.manifest.capability_id, record.manifest.version))
        if handler is None:
            await self._finish(lease_id, "LEASE_FAILED", at)
            raise NodeError("node capability implementation is not bound")
        try:
            output = await asyncio.wait_for(
                handler(request.operation, safe_payload),
                timeout=record.manifest.resource_limits.timeout_seconds,
            )
            safe_output = _safe_payload(output)
        except asyncio.CancelledError:
            await self._finish(lease_id, "LEASE_CANCELLED", at)
            raise
        except Exception as exc:
            await self._finish(lease_id, "LEASE_FAILED", at)
            raise NodeError("node capability execution failed") from exc
        await self._finish(lease_id, "LEASE_COMPLETED", at)
        return NodeExecution(
            lease_id,
            record.manifest.capability_id,
            record.manifest.version,
            request.operation,
            MappingProxyType(safe_output),
        )

    async def _finish(self, lease_id: UUID, kind: str, at: datetime) -> None:
        async with self._lock:
            self._active.discard(lease_id)
            self._store.append(kind, {"lease_id": str(lease_id)}, at)
            if self._state is NodeState.DRAINING and not self._active:
                self._transition(NodeState.STOPPED, at)

    def _transition(self, state: NodeState, at: datetime) -> None:
        self._store.append("STATE_CHANGED", {"from": self._state.value, "to": state.value}, at)
        self._state = state


def _lease_payload(
    lease_id: UUID, record: CapabilityRecord, request: RouteRequest
) -> dict[str, str]:
    return {
        "lease_id": str(lease_id),
        "capability_id": record.manifest.capability_id,
        "version": record.manifest.version,
        "operation": request.operation,
        "manifest_digest": record.manifest.digest,
    }


def _active_leases(events: tuple[dict[str, Any], ...]) -> set[str]:
    active: set[str] = set()
    for event in events:
        payload = event["payload"]
        if event["kind"] == "LEASE_ACQUIRED":
            active.add(str(payload["lease_id"]))
        elif event["kind"] in {
            "LEASE_COMPLETED",
            "LEASE_FAILED",
            "LEASE_CANCELLED",
            "LEASE_ABANDONED",
        }:
            active.discard(str(payload["lease_id"]))
    return active


def _scope(identity: NodePrincipal, required: str) -> None:
    if not isinstance(identity, NodePrincipal) or required not in identity.scopes:
        raise NodeError("node control scope is required")


def _safe_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise NodeError("node payload must be an object")
    try:
        encoded = _canonical(redact(dict(payload)))
        value = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise NodeError("node payload must contain canonical JSON") from exc
    if len(encoded) > _MAX_PAYLOAD or not isinstance(value, dict):
        raise NodeError("node payload is oversized or invalid")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise NodeError("node timestamp must be timezone-aware UTC")
