import asyncio
import json
from datetime import timedelta
from uuid import UUID

import pytest

from nexus_os.agent_controller import AgentControllerError, AgentReasoningController
from nexus_os.agent_store import AgentSessionStore, AgentState
from nexus_os.domain import TaskStatus, TraceId
from nexus_os.model_registry import ModelQualificationRegistry
from nexus_os.providers import ProviderResult
from tests.unit.test_agent_store import SESSION_ID, uid
from tests.unit.test_model_registry import REGISTERED_AT, attestation

CONTROL_AT = REGISTERED_AT + timedelta(minutes=1)


class Ids:
    def __init__(self) -> None:
        self.number = 100

    def candidate_id(self) -> UUID:
        return uid(90)

    def event_id(self) -> UUID:
        self.number += 1
        return uid(self.number)


class Adapter:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.tasks = []

    async def run(self, task):
        self.tasks.append(task)
        return task.provider_task_id

    async def result(self, key):
        return ProviderResult(
            key, TaskStatus.SUCCEEDED, metadata={"output_text": self.outputs.pop(0)}
        )


def proposal(*, ready=True, questions=None):
    return {
        "objective": "Build and verify the accepted reference application.",
        "mode": "app_build",
        "inputs": ["artifact:specifications/reference.pdf"],
        "constraints": ["Do not deploy or publish."],
        "acceptance_criteria": [
            {
                "acceptance_id": "AC-BUILD",
                "statement": "Build succeeds.",
                "verification_method": "runtime_task_evidence",
            }
        ],
        "required_capabilities": ["app_build.planning"],
        "risk_summary": {"highest_effect": "WORKSPACE_WRITE", "reasons": ["Writes source."]},
        "unresolved_questions": [] if questions is None else questions,
        "review_ready": ready,
    }


def setup(tmp_path, outputs, *, qualified=True):
    sessions = AgentSessionStore(tmp_path / "sessions.sqlite")
    sessions.create(
        session_id=SESSION_ID,
        event_id=uid(10),
        project_id="reference_agent",
        objective="Build a reviewed application specification.",
        actor_id="owner-user",
        occurred_at=CONTROL_AT,
    )
    registry = ModelQualificationRegistry(tmp_path / "models.sqlite")
    if qualified:
        registry.register(
            attestation(), registered_at=REGISTERED_AT, registered_by="release-controller"
        )
    adapter = Adapter(outputs)
    controller = AgentReasoningController(
        sessions=sessions,
        qualifications=registry,
        adapter=adapter,
        provider_id="local_openai",
        model_id="reference-model",
        adapter_version="1.0",
        ids=Ids(),
    )
    return controller, sessions, adapter


def test_qualified_model_proposal_becomes_durable_candidate(tmp_path) -> None:
    controller, sessions, adapter = setup(tmp_path, [json.dumps(proposal())])
    result = asyncio.run(
        controller.prepare(
            SESSION_ID,
            actor_id="qualified-agent",
            at=CONTROL_AT,
            expected_sequence=1,
            trace_id=TraceId("7" * 32),
        )
    )
    assert result.state is AgentState.SPECIFICATION_READY
    assert sessions.get_candidate(SESSION_ID).revision == 1
    assert adapter.tasks[0].input["system"].startswith("Return one JSON object only")
    assert "execute work" in adapter.tasks[0].input["system"]


def test_missing_information_persists_clarification_candidate(tmp_path) -> None:
    output = proposal(ready=False, questions=["Which operating system is required?"])
    controller, _, _ = setup(tmp_path, [json.dumps(output)])
    result = asyncio.run(
        controller.prepare(
            SESSION_ID,
            actor_id="qualified-agent",
            at=CONTROL_AT,
            expected_sequence=1,
            trace_id=TraceId("7" * 32),
        )
    )
    assert result.state is AgentState.CLARIFICATION_REQUIRED


def test_invalid_first_output_allows_one_qualified_safe_repair(tmp_path) -> None:
    controller, sessions, adapter = setup(tmp_path, ["not-json", json.dumps(proposal())])
    result = asyncio.run(
        controller.prepare(
            SESSION_ID,
            actor_id="qualified-agent",
            at=CONTROL_AT,
            expected_sequence=1,
            trace_id=TraceId("7" * 32),
        )
    )
    assert result.state is AgentState.SPECIFICATION_READY
    assert len(adapter.tasks) == 2
    assert "not-json" not in adapter.tasks[1].input["prompt"]
    assert sessions.get_candidate(SESSION_ID).revision == 1


def test_two_invalid_outputs_leave_session_unchanged(tmp_path) -> None:
    controller, sessions, _ = setup(tmp_path, ["bad", "still bad"])
    with pytest.raises(AgentControllerError, match="strict candidate"):
        asyncio.run(
            controller.prepare(
                SESSION_ID,
                actor_id="qualified-agent",
                at=CONTROL_AT,
                expected_sequence=1,
                trace_id=TraceId("7" * 32),
            )
        )
    assert sessions.get(SESSION_ID).state is AgentState.DRAFTING
    assert len(sessions.get(SESSION_ID).events) == 1


def test_unqualified_model_is_never_called(tmp_path) -> None:
    controller, sessions, adapter = setup(tmp_path, [json.dumps(proposal())], qualified=False)
    with pytest.raises(AgentControllerError, match="qualification"):
        asyncio.run(
            controller.prepare(
                SESSION_ID,
                actor_id="qualified-agent",
                at=CONTROL_AT,
                expected_sequence=1,
                trace_id=TraceId("7" * 32),
            )
        )
    assert not adapter.tasks
    assert sessions.get(SESSION_ID).state is AgentState.DRAFTING


@pytest.mark.parametrize(
    "output",
    [
        '{"objective":"first","objective":"second"}',
        json.dumps({**proposal(), "tool_call": {"name": "shell"}}),
        json.dumps({**proposal(), "constraints": ["ghp_abcdefghijklmnopqrstuvwxyz1234567890"]}),
        json.dumps({**proposal(), "review_ready": True, "unresolved_questions": ["Contradiction"]}),
    ],
)
def test_hostile_outputs_fail_without_persistence(tmp_path, output) -> None:
    controller, sessions, _ = setup(tmp_path, [output])
    with pytest.raises(AgentControllerError):
        asyncio.run(
            controller.prepare(
                SESSION_ID,
                actor_id="qualified-agent",
                at=CONTROL_AT,
                expected_sequence=1,
                trace_id=TraceId("7" * 32),
                allow_repair=False,
            )
        )
    assert sessions.get(SESSION_ID).state is AgentState.DRAFTING


def test_stale_session_is_rejected_before_provider_call(tmp_path) -> None:
    controller, _, adapter = setup(tmp_path, [json.dumps(proposal())])
    with pytest.raises(AgentControllerError, match="expected drafting"):
        asyncio.run(
            controller.prepare(
                SESSION_ID,
                actor_id="qualified-agent",
                at=CONTROL_AT,
                expected_sequence=0,
                trace_id=TraceId("7" * 32),
            )
        )
    assert not adapter.tasks
