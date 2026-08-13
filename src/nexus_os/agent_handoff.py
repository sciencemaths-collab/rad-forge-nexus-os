"""Deterministic, approval-bound handoff from NEXUS Agent to NEXUS OS."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from nexus_os.agent_store import AgentSessionStore, AgentState, AgentStoreError
from nexus_os.config import LoadedConfig
from nexus_os.domain import RunId, RunState, TraceId
from nexus_os.graph import ValidatedTaskGraph
from nexus_os.modes import AppBuildMode, DataAnalysisMode, ResearchMode
from nexus_os.runtime import RuntimeOrchestrator, RuntimeSnapshot
from nexus_os.stores import SQLiteCheckpointStore


class AgentHandoffError(ValueError):
    """Safe rejection before an unapproved or incompatible run can start."""


@dataclass(frozen=True, slots=True)
class AgentRuntimeHandoff:
    session_id: UUID
    candidate_id: UUID
    candidate_digest: str
    run_id: RunId
    graph_digest: str
    mode: str
    required_capabilities: tuple[str, ...]
    initialized_at: datetime
    state: str = "READY_NOT_EXECUTED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "session_id": str(self.session_id),
            "candidate_id": str(self.candidate_id),
            "candidate_digest": self.candidate_digest,
            "run_id": str(self.run_id),
            "graph_digest": self.graph_digest,
            "mode": self.mode,
            "required_capabilities": list(self.required_capabilities),
            "initialized_at": self.initialized_at.isoformat().replace("+00:00", "Z"),
            "state": self.state,
        }


@dataclass(frozen=True, slots=True)
class HandoffResult:
    handoff: AgentRuntimeHandoff
    graph: ValidatedTaskGraph
    snapshot: RuntimeSnapshot


class AgentRuntimeHandoffService:
    """Compile an approved candidate and initialize, but never dispatch, its run."""

    def __init__(
        self,
        sessions: AgentSessionStore,
        checkpoints: SQLiteCheckpointStore,
    ) -> None:
        self._sessions = sessions
        self._checkpoints = checkpoints
        self._runtime = RuntimeOrchestrator(checkpoints)

    def initialize(
        self,
        session_id: UUID,
        *,
        event_id: UUID,
        actor_id: str,
        expected_sequence: int,
        qualified_capabilities: Iterable[str],
        workspace_root: str,
        trace_id: TraceId,
        now: datetime,
    ) -> HandoffResult:
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise AgentHandoffError("now must be timezone-aware UTC")
        session = self._sessions.get(session_id)
        candidate = self._sessions.get_candidate(session_id)
        if session.state not in {AgentState.APPROVED, AgentState.RUNNING}:
            raise AgentHandoffError("Agent session must contain an approved candidate")
        if session.approved_candidate_digest != candidate.digest:
            raise AgentHandoffError("current candidate does not match the approved digest")
        required = tuple(sorted(candidate.document["required_capabilities"]))
        qualified = frozenset(qualified_capabilities)
        missing = tuple(item for item in required if item not in qualified)
        if missing:
            raise AgentHandoffError("required capabilities are not qualified: " + ",".join(missing))
        if not isinstance(workspace_root, str) or not workspace_root.strip():
            raise AgentHandoffError("workspace_root must be a non-empty path")

        config = _project_config(candidate.document, session.project_id, workspace_root)
        graph = _compiler(candidate.document["mode"]).compile(config)
        run_id = RunId(uuid5(NAMESPACE_URL, f"nexus:agent-run:{candidate.digest}"))
        checkpoint = self._checkpoints.load(
            run_id, graph_digest=graph.graph.digest, schema_version=graph.graph.schema_version
        )
        snapshot = (
            self._runtime.create(run_id=run_id, graph=graph, trace_id=trace_id, now=now)
            if checkpoint is None
            else self._runtime.resume(run_id=run_id, graph=graph)
        )
        if snapshot.run_state is not RunState.READY:
            raise AgentHandoffError("existing runtime handoff is no longer awaiting execution")
        if session.state is AgentState.APPROVED:
            try:
                session = self._sessions.start_run(
                    session_id,
                    event_id=event_id,
                    run_id=run_id.value,
                    candidate_digest=candidate.digest,
                    actor_id=actor_id,
                    occurred_at=now,
                    expected_sequence=expected_sequence,
                )
            except AgentStoreError as exc:
                raise AgentHandoffError(
                    "runtime initialized but session binding must be retried"
                ) from exc
        elif session.run_id != run_id.value:
            raise AgentHandoffError("Agent session is bound to a different runtime run")

        handoff = AgentRuntimeHandoff(
            session_id,
            candidate.candidate_id,
            candidate.digest,
            run_id,
            graph.graph.digest,
            str(candidate.document["mode"]),
            required,
            now,
        )
        return HandoffResult(handoff, graph, snapshot)


def _project_config(
    candidate: dict[str, Any], project_id: str, workspace_root: str
) -> LoadedConfig:
    acceptance = [
        {
            "id": item["acceptance_id"],
            "description": item["statement"],
            "verifier": item["verification_method"],
        }
        for item in candidate["acceptance_criteria"]
    ]
    document = {
        "schema_version": "1.0",
        "project_id": project_id,
        "name": "NEXUS Agent approved run",
        "mode": candidate["mode"],
        "goal": candidate["objective"],
        "workspace": {"root": workspace_root, "read_only": False, "network_allowlist": []},
        "providers": {"reasoning": {"adapter": "runtime-selected", "fallback": []}},
        "secrets": {},
        "policy": {
            "max_attempts": 3,
            "max_elapsed_seconds": 86400,
            "max_cost_usd": 0,
            "require_approval": ["SENSITIVE", "DESTRUCTIVE"],
        },
        "acceptance": acceptance,
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    return LoadedConfig(MappingProxyType(document), canonical, digest)


def _compiler(mode: str) -> AppBuildMode | ResearchMode | DataAnalysisMode:
    if mode == "app_build":
        return AppBuildMode()
    if mode == "research":
        return ResearchMode()
    if mode == "data_analysis":
        return DataAnalysisMode()
    raise AgentHandoffError("candidate mode is unsupported")
