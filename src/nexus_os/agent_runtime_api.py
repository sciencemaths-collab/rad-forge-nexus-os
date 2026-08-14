"""Authenticated API composition for the governed Agent runtime lifecycle."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from uuid import UUID

from nexus_os.agent_api import AgentApiRequest, AgentIdentity, ApplicationIds
from nexus_os.agent_handoff import AgentRuntimeHandoffService
from nexus_os.agent_store import AgentSessionStore
from nexus_os.approval import ApprovalRecord, ApprovalStatus, ApprovalStore
from nexus_os.domain import TaskId
from nexus_os.evidence import EvidenceLedger
from nexus_os.graph import ValidatedTaskGraph, compile_task_graph, validate_task_graph
from nexus_os.runtime import RuntimeOrchestrator, RuntimeSnapshot
from nexus_os.runtime_evidence import AgentCompletionVerifier
from nexus_os.scheduler import GovernedScheduler, SchedulerTickResult


class AgentRuntimeApiError(ValueError):
    """Safe runtime API state, authorization, or persistence failure."""


class CapabilityAuthorizer(Protocol):
    def qualified_capabilities(
        self, identity: AgentIdentity, session_id: UUID
    ) -> frozenset[str]: ...


class AgentRuntimeRegistry:
    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS agent_runtime_graphs (
            session_id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE,
            graph_json TEXT NOT NULL, graph_digest TEXT NOT NULL)"""
        )

    def save(self, session_id: UUID, snapshot: RuntimeSnapshot) -> None:
        graph_json = json.dumps(
            snapshot.graph.graph.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        try:
            self._connection.execute(
                "INSERT INTO agent_runtime_graphs VALUES (?, ?, ?, ?)",
                (
                    str(session_id),
                    str(snapshot.run_id),
                    graph_json,
                    snapshot.graph.graph.digest,
                ),
            )
        except sqlite3.IntegrityError:
            existing = self.load(session_id)
            if existing.graph.digest != snapshot.graph.graph.digest or str(
                snapshot.run_id
            ) != self.run_id(session_id):
                raise AgentRuntimeApiError("runtime registry binding conflicts") from None

    def load(self, session_id: UUID) -> ValidatedTaskGraph:
        row = self._row(session_id)
        try:
            graph = validate_task_graph(compile_task_graph(json.loads(str(row[2]))))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AgentRuntimeApiError("stored runtime graph failed validation") from exc
        if graph.graph.digest != str(row[3]):
            raise AgentRuntimeApiError("stored runtime graph digest is invalid")
        return graph

    def run_id(self, session_id: UUID) -> str:
        return str(self._row(session_id)[1])

    def _row(self, session_id: UUID) -> tuple[object, ...]:
        row = self._connection.execute(
            "SELECT * FROM agent_runtime_graphs WHERE session_id=?", (str(session_id),)
        ).fetchone()
        if row is None:
            raise AgentRuntimeApiError("runtime is not initialized")
        return tuple(row)


class GovernedAgentRuntimeApi:
    def __init__(
        self,
        *,
        sessions: AgentSessionStore,
        handoff: AgentRuntimeHandoffService,
        registry: AgentRuntimeRegistry,
        runtime: RuntimeOrchestrator,
        scheduler: GovernedScheduler,
        approvals: ApprovalStore,
        evidence: EvidenceLedger,
        completion: AgentCompletionVerifier,
        capabilities: CapabilityAuthorizer,
        ids: ApplicationIds,
    ) -> None:
        self._sessions = sessions
        self._handoff = handoff
        self._registry = registry
        self._runtime = runtime
        self._scheduler = scheduler
        self._approvals = approvals
        self._evidence = evidence
        self._completion = completion
        self._capabilities = capabilities
        self._ids = ids

    def start(
        self,
        session_id: UUID,
        identity: AgentIdentity,
        request: AgentApiRequest,
        body: dict[str, object],
    ) -> Mapping[str, object]:
        result = self._handoff.initialize(
            session_id,
            event_id=self._ids.event_id(),
            actor_id=identity.actor_id,
            expected_sequence=len(self._sessions.get(session_id).events),
            qualified_capabilities=self._capabilities.qualified_capabilities(identity, session_id),
            workspace_root=str(body["workspace_root"]),
            trace_id=request.trace_id,
            now=request.occurred_at,
        )
        self._registry.save(session_id, result.snapshot)
        return _snapshot(result.snapshot)

    def status(self, session_id: UUID) -> Mapping[str, object]:
        return _snapshot(self._snapshot(session_id))

    def preview(
        self, session_id: UUID, identity: AgentIdentity, task_id: str | None = None
    ) -> Mapping[str, object]:
        task, preview = self._scheduler.preview(
            self._snapshot(session_id),
            actor_id=identity.actor_id,
            task_id=None if task_id is None else TaskId(task_id),
        )
        return {
            "task_id": str(task.task_id),
            "task_kind": task.kind,
            "tool_name": preview.tool_name,
            "effect": preview.effect.value,
            "input": dict(task.input),
            "input_digest": preview.input_digest,
            "action_digest": preview.action_digest,
            "decision": preview.decision.value,
            "approval_required": preview.approval_required,
            "reason_codes": list(preview.reason_codes),
        }

    def evidence(self, session_id: UUID) -> Mapping[str, object]:
        snapshot = self._snapshot(session_id)
        records = self._evidence.records(snapshot.graph.graph.project_id, snapshot.run_id)
        verification = (
            None
            if not records
            else self._evidence.verify(snapshot.graph.graph.project_id, snapshot.run_id)
        )
        return {
            "run_id": str(snapshot.run_id),
            "record_count": len(records),
            "chain_status": "EMPTY" if verification is None else "VERIFIED",
            "head_hash": None if verification is None else verification.head_hash,
            "records": [record.to_dict() for record in records],
        }

    async def tick(
        self,
        session_id: UUID,
        identity: AgentIdentity,
        request: AgentApiRequest,
        body: dict[str, object] | None,
    ) -> Mapping[str, object]:
        values = body or {}
        approval_id = UUID(str(values["approval_id"])) if "approval_id" in values else None
        task_id = TaskId(str(values["task_id"])) if "task_id" in values else None
        result = await self._scheduler.tick(
            self._snapshot(session_id),
            actor_id=identity.actor_id,
            trace_id=request.trace_id,
            now=request.occurred_at,
            approval_id=approval_id,
            task_id=task_id,
        )
        return _tick(result)

    def decide_approval(
        self,
        session_id: UUID,
        approval_id: UUID,
        identity: AgentIdentity,
        request: AgentApiRequest,
        body: dict[str, object],
    ) -> Mapping[str, object]:
        if not identity.human:
            raise AgentRuntimeApiError("human approval principal is required")
        record = self._approvals.get(approval_id)
        if record.run_id.value != UUID(self._registry.run_id(session_id)):
            raise AgentRuntimeApiError("approval does not belong to Agent runtime")
        decided = self._approvals.decide(
            approval_id,
            status=ApprovalStatus(str(body["status"])),
            decided_by=identity.actor_id,
            decided_at=request.occurred_at,
            reason=None if body.get("reason") is None else str(body["reason"]),
        )
        return _approval(decided)

    def verify(
        self, session_id: UUID, identity: AgentIdentity, request: AgentApiRequest
    ) -> Mapping[str, object]:
        passed = self._completion.verify(
            session_id,
            self._snapshot(session_id),
            start_event_id=self._ids.event_id(),
            completion_event_id=self._ids.event_id(),
            actor_id=identity.actor_id,
            trace_id=request.trace_id,
            now=request.occurred_at,
            expected_sequence=len(self._sessions.get(session_id).events),
        )
        return {"passed": passed, "session": self._sessions.get(session_id).to_dict()}

    def _snapshot(self, session_id: UUID) -> RuntimeSnapshot:
        graph = self._registry.load(session_id)
        from nexus_os.domain import RunId

        return self._runtime.inspect(
            run_id=RunId.parse(self._registry.run_id(session_id)), graph=graph
        )


def _snapshot(snapshot: RuntimeSnapshot) -> dict[str, object]:
    return {
        "run_id": str(snapshot.run_id),
        "graph_digest": snapshot.graph.graph.digest,
        "run_state": snapshot.run_state.value,
        "task_states": {str(key): value.value for key, value in snapshot.task_states.items()},
        "revision": snapshot.revision,
    }


def _tick(result: SchedulerTickResult) -> dict[str, object]:
    value: dict[str, object] = {
        "outcome": result.outcome.value,
        "runtime": _snapshot(result.snapshot),
    }
    if result.task_id is not None:
        value["task_id"] = str(result.task_id)
    if result.approval is not None:
        value["approval"] = _approval(result.approval)
    if result.retry_decision is not None:
        value["retry"] = {
            "action": result.retry_decision.action.value,
            "reason": result.retry_decision.reason,
            "next_attempt": result.retry_decision.next_attempt,
            "delay_seconds": result.retry_decision.delay_seconds,
        }
    return value


def _approval(record: ApprovalRecord) -> dict[str, object]:
    return {
        "approval_id": str(record.approval_id),
        "run_id": str(record.run_id),
        "action_digest": record.action_digest,
        "effect": record.effect.value,
        "status": record.status.value,
        "expires_at": record.expires_at.isoformat().replace("+00:00", "Z"),
    }
