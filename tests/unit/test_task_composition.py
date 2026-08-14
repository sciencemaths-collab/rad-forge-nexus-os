import asyncio
import sqlite3
from datetime import UTC, datetime

import pytest

from nexus_os.domain import ActionEffect, RunId, TaskDefinition, TaskId, TraceId
from nexus_os.task_composition import ReasonedTaskCompositionStore, TaskCompositionError
from nexus_os.task_reasoning import ReasonedTaskArtifact

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
RUN = RunId.parse("95000000-0000-4000-8000-000000000001")
OTHER_RUN = RunId.parse("95000000-0000-4000-8000-000000000002")
TRACE = TraceId("5" * 32)


class Reasoner:
    def __init__(self, artifact: ReasonedTaskArtifact) -> None:
        self.artifact = artifact
        self.calls = 0

    async def propose(self, task, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return self.artifact


def artifact(*, questions: tuple[str, ...] = ()) -> ReasonedTaskArtifact:
    return ReasonedTaskArtifact(
        "Approved proposal",
        "Use the approved input only.",
        (("Scope", "Create the bounded artifact."),),
        ("Verify the typed-tool outcome.",),
        questions,
    )


def task(input_value=None) -> TaskDefinition:  # type: ignore[no-untyped-def]
    return TaskDefinition(
        TaskId("specification"),
        "mode.app_build.specification",
        (),
        ActionEffect.WORKSPACE_WRITE,
        60,
        1,
        0,
        input_value or {"goal": "Create spec.md"},
    )


def store(tmp_path, result=None):  # type: ignore[no-untyped-def]
    reasoner = Reasoner(result or artifact())
    return ReasonedTaskCompositionStore(tmp_path / "composition.db", reasoner), reasoner


def test_prepare_and_resolve_are_exact_deterministic_and_durable(tmp_path) -> None:
    subject, reasoner = store(tmp_path)
    prepared = asyncio.run(subject.prepare(task(), run_id=RUN, trace_id=TRACE, at=NOW))
    first = subject.resolve(RUN, task())
    second = subject.resolve(RUN, task())
    assert prepared.digest == first["reasoned_artifact_digest"]
    assert first == second
    assert first["goal"] == "Create spec.md"
    assert set(first) == {"goal", "reasoned_artifact", "reasoned_artifact_digest"}
    assert reasoner.calls == 1


def test_missing_or_drifted_exact_binding_fails_closed(tmp_path) -> None:
    subject, _ = store(tmp_path)
    with pytest.raises(TaskCompositionError, match="missing"):
        subject.resolve(RUN, task())
    asyncio.run(subject.prepare(task(), run_id=RUN, trace_id=TRACE, at=NOW))
    with pytest.raises(TaskCompositionError, match="does not match"):
        subject.resolve(RUN, task({"goal": "Changed after approval"}))
    with pytest.raises(TaskCompositionError, match="missing"):
        subject.resolve(OTHER_RUN, task())


def test_unresolved_questions_are_never_persisted_or_executed(tmp_path) -> None:
    subject, _ = store(tmp_path, artifact(questions=("Which file?",)))
    with pytest.raises(TaskCompositionError, match="unresolved"):
        asyncio.run(subject.prepare(task(), run_id=RUN, trace_id=TRACE, at=NOW))
    with pytest.raises(TaskCompositionError, match="missing"):
        subject.resolve(RUN, task())


@pytest.mark.parametrize("reserved", ["reasoned_artifact", "reasoned_artifact_digest"])
def test_approved_input_cannot_spoof_reserved_composition_fields(tmp_path, reserved) -> None:  # type: ignore[no-untyped-def]
    subject, reasoner = store(tmp_path)
    with pytest.raises(TaskCompositionError, match="reserved"):
        asyncio.run(
            subject.prepare(
                task({"goal": "x", reserved: "spoof"}), run_id=RUN, trace_id=TRACE, at=NOW
            )
        )
    assert reasoner.calls == 0


def test_immutable_store_rejects_rebinding_and_detects_tampering(tmp_path) -> None:
    path = tmp_path / "composition.db"
    reasoner = Reasoner(artifact())
    subject = ReasonedTaskCompositionStore(path, reasoner)  # type: ignore[arg-type]
    asyncio.run(subject.prepare(task(), run_id=RUN, trace_id=TRACE, at=NOW))
    reasoner.artifact = ReasonedTaskArtifact(
        "Different", "Different proposal.", (("Scope", "Different."),), (), ()
    )
    with pytest.raises(TaskCompositionError, match="already exists"):
        asyncio.run(subject.prepare(task(), run_id=RUN, trace_id=TRACE, at=NOW))
    connection = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute("UPDATE reasoned_task_compositions SET artifact_digest='sha256:bad'")
