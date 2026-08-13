import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from nexus_os.agent_handoff import AgentHandoffError, AgentRuntimeHandoffService
from nexus_os.agent_store import (
    AgentSessionStore,
    CandidateSpecification,
    ReviewPrincipal,
    candidate_digest,
)
from nexus_os.domain import RunState, TraceId
from nexus_os.stores import SQLiteCheckpointStore

SESSION = UUID("81000000-0000-4000-8000-000000000001")
CANDIDATE = UUID("81000000-0000-4000-8000-000000000002")
NOW = datetime(2026, 8, 13, 20, tzinfo=UTC)
TRACE = TraceId("1234567890abcdef1234567890abcdef")


def _id(number: int) -> UUID:
    return UUID(f"81000000-0000-4000-8000-{number:012d}")


def _document(*, capabilities=("app_build.planning",)) -> dict:
    unsigned = {
        "schema_version": "1.0",
        "candidate_id": str(CANDIDATE),
        "session_id": str(SESSION),
        "revision": 1,
        "objective": "Build and verify the approved application.",
        "mode": "app_build",
        "inputs": ["artifact:specifications/approved.md"],
        "constraints": ["Do not deploy."],
        "acceptance_criteria": [
            {
                "acceptance_id": "AC-BUILD",
                "statement": "All declared tests pass.",
                "verification_method": "Run the locked test gates.",
            }
        ],
        "required_capabilities": list(capabilities),
        "risk_summary": {"highest_effect": "WORKSPACE_WRITE", "reasons": ["Writes files."]},
        "unresolved_questions": [],
        "review_ready": True,
    }
    return {**unsigned, "candidate_digest": candidate_digest(unsigned)}


def _approved(store: AgentSessionStore, document: dict | None = None) -> CandidateSpecification:
    spec = CandidateSpecification.parse(document or _document())
    store.create(
        session_id=SESSION,
        event_id=_id(10),
        project_id="agent_handoff",
        objective="Build the approved project.",
        actor_id="owner-user",
        occurred_at=NOW,
    )
    store.save_candidate(
        spec, event_id=_id(11), actor_id="qualified-agent", occurred_at=NOW, expected_sequence=1
    )
    store.start_review(
        SESSION, event_id=_id(12), actor_id="agent-service", occurred_at=NOW, expected_sequence=2
    )
    store.approve(
        SESSION,
        event_id=_id(13),
        candidate_digest=spec.digest,
        principal=ReviewPrincipal("owner-reviewer", True, True),
        occurred_at=NOW,
        expected_sequence=3,
    )
    return spec


def test_approved_candidate_compiles_and_initializes_without_dispatch(tmp_path) -> None:
    sessions = AgentSessionStore(tmp_path / "agent.db")
    checkpoints = SQLiteCheckpointStore(tmp_path / "runtime.db")
    spec = _approved(sessions)
    result = AgentRuntimeHandoffService(sessions, checkpoints).initialize(
        SESSION,
        event_id=_id(14),
        actor_id="handoff-service",
        expected_sequence=4,
        qualified_capabilities={"app_build.planning"},
        workspace_root="/workspace/project",
        trace_id=TRACE,
        now=NOW + timedelta(minutes=1),
    )
    assert result.snapshot.run_state is RunState.READY
    assert all(
        value.value in {"READY", "PENDING"} for value in result.snapshot.task_states.values()
    )
    assert result.handoff.candidate_digest == spec.digest
    assert sessions.get(SESSION).run_id == result.snapshot.run_id.value
    schema = json.loads(Path("schemas/agent-runtime-handoff.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result.handoff.to_dict())


def test_handoff_is_deterministic_and_resumable(tmp_path) -> None:
    sessions = AgentSessionStore(tmp_path / "agent.db")
    checkpoints = SQLiteCheckpointStore(tmp_path / "runtime.db")
    _approved(sessions)
    service = AgentRuntimeHandoffService(sessions, checkpoints)
    first = service.initialize(
        SESSION,
        event_id=_id(14),
        actor_id="handoff-service",
        expected_sequence=4,
        qualified_capabilities={"app_build.planning"},
        workspace_root="/workspace/project",
        trace_id=TRACE,
        now=NOW,
    )
    second = service.initialize(
        SESSION,
        event_id=_id(15),
        actor_id="handoff-service",
        expected_sequence=5,
        qualified_capabilities={"app_build.planning"},
        workspace_root="/workspace/project",
        trace_id=TRACE,
        now=NOW,
    )
    assert second.snapshot.run_id == first.snapshot.run_id
    assert second.graph.graph.digest == first.graph.graph.digest
    assert len(sessions.get(SESSION).events) == 5


def test_missing_qualification_fails_before_checkpoint_or_session_transition(tmp_path) -> None:
    sessions = AgentSessionStore(tmp_path / "agent.db")
    checkpoints = SQLiteCheckpointStore(tmp_path / "runtime.db")
    _approved(sessions, _document(capabilities=("app_build.planning", "tools.workspace")))
    with pytest.raises(AgentHandoffError, match="not qualified"):
        AgentRuntimeHandoffService(sessions, checkpoints).initialize(
            SESSION,
            event_id=_id(14),
            actor_id="handoff-service",
            expected_sequence=4,
            qualified_capabilities={"app_build.planning"},
            workspace_root="/workspace/project",
            trace_id=TRACE,
            now=NOW,
        )
    assert sessions.get(SESSION).state.value == "APPROVED"
