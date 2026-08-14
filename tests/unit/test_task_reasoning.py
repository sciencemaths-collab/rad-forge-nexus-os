import asyncio
import json
from datetime import timedelta

import pytest

from nexus_os.domain import ActionEffect, RunId, TaskDefinition, TaskId, TaskStatus, TraceId
from nexus_os.model_registry import ModelQualificationRegistry
from nexus_os.providers import ProviderResult
from nexus_os.task_reasoning import QualifiedTaskReasoner, TaskReasoningError
from tests.unit.test_model_registry import REGISTERED_AT, attestation

NOW = REGISTERED_AT + timedelta(minutes=1)
RUN = RunId.parse("94000000-0000-4000-8000-000000000001")
TRACE = TraceId("4" * 32)


class Adapter:
    def __init__(self, outputs):  # type: ignore[no-untyped-def]
        self.outputs = list(outputs)
        self.tasks = []

    async def run(self, task):  # type: ignore[no-untyped-def]
        self.tasks.append(task)
        return task.provider_task_id

    async def result(self, key):  # type: ignore[no-untyped-def]
        return ProviderResult(
            key, TaskStatus.SUCCEEDED, metadata={"output_text": self.outputs.pop(0)}
        )


def output() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "title": "Approved task proposal",
        "summary": "A bounded proposal for deterministic validation.",
        "sections": [{"heading": "Scope", "content": "Use only the approved task input."}],
        "evidence_notes": ["Requires typed-tool outcome evidence."],
        "unresolved_questions": [],
    }


def task(effect: ActionEffect = ActionEffect.WORKSPACE_WRITE) -> TaskDefinition:
    return TaskDefinition(
        TaskId("specification"),
        "mode.app_build.specification",
        (),
        effect,
        60,
        1,
        0,
        {"goal": "Create the approved specification.", "expected_artifact": "spec.md"},
    )


def reasoner(tmp_path, outputs, *, qualified=True):  # type: ignore[no-untyped-def]
    registry = ModelQualificationRegistry(tmp_path / "models.sqlite")
    if qualified:
        registry.register(attestation(), registered_at=REGISTERED_AT, registered_by="tester")
    adapter = Adapter(outputs)
    return (
        QualifiedTaskReasoner(
            qualifications=registry,
            adapter=adapter,
            provider_id="local_openai",
            model_id="reference-model",
            adapter_version="1.0",
        ),
        adapter,
    )


def test_qualified_task_proposal_is_strict_digest_bound_and_side_effect_free(tmp_path) -> None:
    controller, adapter = reasoner(tmp_path, [json.dumps(output())])
    result = asyncio.run(controller.propose(task(), run_id=RUN, trace_id=TRACE, at=NOW))
    assert result.title == "Approved task proposal"
    assert result.digest.startswith("sha256:")
    assert adapter.tasks[0].operation == "task_planning"
    assert adapter.tasks[0].run_id == RUN
    assert adapter.tasks[0].task_id == TaskId("specification")
    assert "do not call tools" in adapter.tasks[0].input["system"]


def test_unqualified_model_is_not_called_for_task_reasoning(tmp_path) -> None:
    controller, adapter = reasoner(tmp_path, [json.dumps(output())], qualified=False)
    with pytest.raises(TaskReasoningError, match="qualification"):
        asyncio.run(controller.propose(task(), run_id=RUN, trace_id=TRACE, at=NOW))
    assert adapter.tasks == []


def test_one_separately_qualified_repair_does_not_reflect_invalid_output(tmp_path) -> None:
    controller, adapter = reasoner(tmp_path, ["not-json", json.dumps(output())])
    result = asyncio.run(controller.propose(task(), run_id=RUN, trace_id=TRACE, at=NOW))
    assert result.digest.startswith("sha256:")
    assert len(adapter.tasks) == 2
    assert "not-json" not in adapter.tasks[1].input["prompt"]
    assert "failed validation" in adapter.tasks[1].input["prompt"]


@pytest.mark.parametrize(
    "invalid",
    [
        '{"schema_version":"1.0","title":"one","title":"two"}',
        json.dumps({**output(), "tool_call": {"name": "shell"}}),
        json.dumps({**output(), "summary": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"}),
        json.dumps({**output(), "sections": []}),
        json.dumps({**output(), "title": "x" * 201}),
    ],
)
def test_hostile_or_invalid_task_outputs_fail_closed(tmp_path, invalid) -> None:  # type: ignore[no-untyped-def]
    controller, _ = reasoner(tmp_path, [invalid])
    with pytest.raises(TaskReasoningError, match="strict validation"):
        asyncio.run(
            controller.propose(task(), run_id=RUN, trace_id=TRACE, at=NOW, allow_repair=False)
        )


def test_sensitive_task_requires_sensitive_action_model_use(tmp_path) -> None:
    controller, adapter = reasoner(tmp_path, [json.dumps(output())])
    result = asyncio.run(
        controller.propose(task(ActionEffect.SENSITIVE), run_id=RUN, trace_id=TRACE, at=NOW)
    )
    assert result.title == "Approved task proposal"
    assert len(adapter.tasks) == 1


def test_secret_like_or_oversized_task_input_is_never_sent(tmp_path) -> None:
    controller, adapter = reasoner(tmp_path, [json.dumps(output())])
    for value, message in (
        ("ghp_abcdefghijklmnopqrstuvwxyz1234567890", "secret-like"),
        ("x" * 70_000, "exceeds"),
    ):
        unsafe = TaskDefinition(
            TaskId("specification"),
            "mode.app_build.specification",
            (),
            ActionEffect.WORKSPACE_WRITE,
            60,
            1,
            0,
            {"goal": value},
        )
        with pytest.raises(TaskReasoningError, match=message):
            asyncio.run(controller.propose(unsafe, run_id=RUN, trace_id=TRACE, at=NOW))
    assert adapter.tasks == []
