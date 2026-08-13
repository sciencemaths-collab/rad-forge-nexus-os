from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from nexus_os.agent_store import (
    AgentSessionStore,
    AgentState,
    AgentStoreConflict,
    AgentStoreError,
    CandidateSpecification,
    ReviewPrincipal,
    candidate_digest,
)

SESSION_ID = UUID("70000000-0000-4000-8000-000000000001")
CANDIDATE_ID = UUID("70000000-0000-4000-8000-000000000002")
AT = datetime(2026, 8, 13, 18, tzinfo=UTC)


def uid(number: int) -> UUID:
    return UUID(f"70000000-0000-4000-8000-{number:012d}")


def candidate(*, revision: int = 1, ready: bool = True, questions=None, **changes):
    unsigned = {
        "schema_version": "1.0",
        "candidate_id": str(CANDIDATE_ID),
        "session_id": str(SESSION_ID),
        "revision": revision,
        "objective": "Build and verify the accepted reference application.",
        "mode": "app_build",
        "inputs": ["artifact:specifications/reference.pdf"],
        "constraints": ["Do not deploy or publish."],
        "acceptance_criteria": [
            {
                "acceptance_id": "AC-BUILD",
                "statement": "The locked build succeeds.",
                "verification_method": "Run the declared build gate.",
            }
        ],
        "required_capabilities": ["app_build.planning"],
        "risk_summary": {"highest_effect": "WORKSPACE_WRITE", "reasons": ["Writes source."]},
        "unresolved_questions": [] if questions is None else questions,
        "review_ready": ready,
    }
    unsigned.update(changes)
    return {**unsigned, "candidate_digest": candidate_digest(unsigned)}


def created(store: AgentSessionStore):
    return store.create(
        session_id=SESSION_ID,
        event_id=uid(10),
        project_id="reference_agent",
        objective="Build a reviewed application specification.",
        actor_id="owner-user",
        occurred_at=AT,
    )


def test_complete_review_and_digest_bound_approval_lifecycle(tmp_path) -> None:
    store = AgentSessionStore(tmp_path / "agent.sqlite")
    assert created(store).state is AgentState.DRAFTING
    spec = CandidateSpecification.parse(candidate())
    prepared = store.save_candidate(
        spec,
        event_id=uid(11),
        actor_id="qualified-agent",
        occurred_at=AT + timedelta(minutes=1),
        expected_sequence=1,
    )
    assert prepared.state is AgentState.SPECIFICATION_READY
    review = store.start_review(
        SESSION_ID,
        event_id=uid(12),
        actor_id="agent-service",
        occurred_at=AT + timedelta(minutes=2),
        expected_sequence=2,
    )
    approved = store.approve(
        SESSION_ID,
        event_id=uid(13),
        candidate_digest=spec.digest,
        principal=ReviewPrincipal("owner-reviewer", True, True),
        occurred_at=AT + timedelta(minutes=3),
        expected_sequence=3,
    )
    assert review.state is AgentState.USER_REVIEW
    assert approved.state is AgentState.APPROVED
    assert approved.approved_candidate_digest == spec.digest
    assert [event.sequence for event in approved.events] == [1, 2, 3, 4]


def test_unresolved_candidate_requires_clarification_then_revision(tmp_path) -> None:
    store = AgentSessionStore(tmp_path / "agent.sqlite")
    created(store)
    first = CandidateSpecification.parse(
        candidate(ready=False, questions=["Which operating system is required?"])
    )
    assert (
        store.save_candidate(
            first,
            event_id=uid(11),
            actor_id="qualified-agent",
            occurred_at=AT + timedelta(minutes=1),
            expected_sequence=1,
        ).state
        is AgentState.CLARIFICATION_REQUIRED
    )
    assert (
        store.receive_clarification(
            SESSION_ID,
            event_id=uid(12),
            actor_id="owner-user",
            occurred_at=AT + timedelta(minutes=2),
            expected_sequence=2,
        ).state
        is AgentState.DRAFTING
    )
    second = CandidateSpecification.parse(candidate(revision=2))
    result = store.save_candidate(
        second,
        event_id=uid(13),
        actor_id="qualified-agent",
        occurred_at=AT + timedelta(minutes=3),
        expected_sequence=3,
    )
    assert result.state is AgentState.SPECIFICATION_READY
    assert store.get_candidate(SESSION_ID).revision == 2


def test_stale_sequence_rejected_without_partial_event(tmp_path) -> None:
    store = AgentSessionStore(tmp_path / "agent.sqlite")
    created(store)
    with pytest.raises(AgentStoreConflict, match="sequence conflict"):
        store.save_candidate(
            CandidateSpecification.parse(candidate()),
            event_id=uid(11),
            actor_id="qualified-agent",
            occurred_at=AT,
            expected_sequence=0,
        )
    assert len(store.get(SESSION_ID).events) == 1


def test_wrong_digest_and_unauthorized_principal_cannot_approve(tmp_path) -> None:
    store = AgentSessionStore(tmp_path / "agent.sqlite")
    created(store)
    spec = CandidateSpecification.parse(candidate())
    store.save_candidate(
        spec, event_id=uid(11), actor_id="qualified-agent", occurred_at=AT, expected_sequence=1
    )
    store.start_review(
        SESSION_ID, event_id=uid(12), actor_id="agent-service", occurred_at=AT, expected_sequence=2
    )
    with pytest.raises(AgentStoreError, match="does not match"):
        store.approve(
            SESSION_ID,
            event_id=uid(13),
            candidate_digest="0" * 64,
            principal=ReviewPrincipal("owner-reviewer", True, True),
            occurred_at=AT,
            expected_sequence=3,
        )
    with pytest.raises(AgentStoreError, match="authenticated authorized"):
        store.approve(
            SESSION_ID,
            event_id=uid(14),
            candidate_digest=spec.digest,
            principal=ReviewPrincipal("owner-reviewer", True, False),
            occurred_at=AT,
            expected_sequence=3,
        )
    assert store.get(SESSION_ID).state is AgentState.USER_REVIEW


@pytest.mark.parametrize(
    "change",
    [
        {"candidate_digest": "0" * 64},
        {"review_ready": True, "unresolved_questions": ["Still unknown"]},
        {"inputs": ["env:SECRET"]},
        {
            "acceptance_criteria": [
                {"acceptance_id": "AC-X", "statement": "One", "verification_method": "Check"},
                {"acceptance_id": "AC-X", "statement": "Two", "verification_method": "Check"},
            ]
        },
    ],
)
def test_hostile_or_noncanonical_candidate_is_rejected(change) -> None:
    document = candidate()
    document.update(change)
    with pytest.raises(AgentStoreError, match="canonical validation"):
        CandidateSpecification.parse(document)


def test_revision_identity_and_number_are_monotonic(tmp_path) -> None:
    store = AgentSessionStore(tmp_path / "agent.sqlite")
    created(store)
    first = CandidateSpecification.parse(candidate(ready=False, questions=["Need input"]))
    store.save_candidate(
        first, event_id=uid(11), actor_id="qualified-agent", occurred_at=AT, expected_sequence=1
    )
    store.receive_clarification(
        SESSION_ID, event_id=uid(12), actor_id="owner-user", occurred_at=AT, expected_sequence=2
    )
    with pytest.raises(AgentStoreError, match="monotonic"):
        store.save_candidate(
            CandidateSpecification.parse(candidate(revision=3)),
            event_id=uid(13),
            actor_id="qualified-agent",
            occurred_at=AT,
            expected_sequence=3,
        )


def test_event_chronology_cannot_move_backwards(tmp_path) -> None:
    store = AgentSessionStore(tmp_path / "agent.sqlite")
    created(store)
    with pytest.raises(AgentStoreError, match="chronology"):
        store.save_candidate(
            CandidateSpecification.parse(candidate()),
            event_id=uid(11),
            actor_id="qualified-agent",
            occurred_at=AT - timedelta(seconds=1),
            expected_sequence=1,
        )


def test_terminal_or_wrong_state_operation_fails_closed(tmp_path) -> None:
    store = AgentSessionStore(tmp_path / "agent.sqlite")
    created(store)
    with pytest.raises(AgentStoreError, match="state does not permit"):
        store.start_review(
            SESSION_ID,
            event_id=uid(11),
            actor_id="agent-service",
            occurred_at=AT,
            expected_sequence=1,
        )
