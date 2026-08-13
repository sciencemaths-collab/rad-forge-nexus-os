import asyncio
from datetime import timedelta

from nexus_os.attempt_store import AttemptStore
from nexus_os.domain import TaskId, TaskStatus
from nexus_os.evidence import EvidenceLedger
from nexus_os.retry import RetryEngine, RetryLimits
from nexus_os.runtime_evidence import RuntimeEvidenceWriter
from nexus_os.scheduler import GovernedScheduler, SchedulerOutcome
from nexus_os.tools import ToolExecutor
from tests.contract.test_governed_scheduler_contract import NOW, TRACE, _subject


def test_transient_failure_is_evidenced_and_rescheduled_then_succeeds(tmp_path) -> None:
    scheduler, snapshot, approvals, calls = _subject(tmp_path, max_attempts=3)
    attempts = AttemptStore(tmp_path / "retry-attempts.db")
    failures = 1

    async def handler(payload):
        nonlocal failures
        calls.append(payload)
        if failures:
            failures -= 1
            raise OSError("synthetic unavailable")
        return {"accepted": True}

    scheduler._registry._handlers["nexus.test.execute"] = handler
    scheduler = GovernedScheduler(
        runtime=scheduler._runtime,
        registry=scheduler._registry,
        executor=ToolExecutor(scheduler._registry, scheduler._policy, approvals),
        policy=scheduler._policy,
        approvals=approvals,
        attempts=attempts,
        retry=RetryEngine(RetryLimits(max_attempts=3)),
        evidence=RuntimeEvidenceWriter(EvidenceLedger(tmp_path / "retry-evidence.db")),
        tool_bindings={"mode.test.execute": "nexus.test.execute"},
    )
    first = asyncio.run(
        scheduler.tick(
            snapshot,
            actor_id="runtime-scheduler",
            trace_id=TRACE,
            now=NOW,
            attempt_elapsed=timedelta(seconds=2),
        )
    )
    assert first.outcome is SchedulerOutcome.RETRY_SCHEDULED
    assert first.snapshot.task_states[TaskId("first_task")] is TaskStatus.READY
    assert len(attempts.history(snapshot.run_id, TaskId("first_task"))) == 1
    second = asyncio.run(
        scheduler.tick(first.snapshot, actor_id="runtime-scheduler", trace_id=TRACE, now=NOW)
    )
    assert second.outcome is SchedulerOutcome.SUCCEEDED


def test_graph_attempt_ceiling_stops_even_when_global_limit_is_higher(tmp_path) -> None:
    scheduler, snapshot, _, calls = _subject(tmp_path)

    async def handler(payload):
        calls.append(payload)
        raise OSError("synthetic unavailable")

    scheduler._registry._handlers["nexus.test.execute"] = handler
    result = asyncio.run(
        scheduler.tick(snapshot, actor_id="runtime-scheduler", trace_id=TRACE, now=NOW)
    )
    assert result.outcome is SchedulerOutcome.FAILED
    assert result.retry_decision is not None
    assert result.retry_decision.reason == "task attempt limit reached"


def test_invalid_tool_output_requires_repair_without_mutating_approved_input(tmp_path) -> None:
    scheduler, snapshot, approvals, calls = _subject(tmp_path, max_attempts=3)
    attempts = AttemptStore(tmp_path / "repair-attempts.db")

    async def handler(payload):
        calls.append(payload)
        return {"wrong": True}

    scheduler._registry._handlers["nexus.test.execute"] = handler
    scheduler = GovernedScheduler(
        runtime=scheduler._runtime,
        registry=scheduler._registry,
        executor=ToolExecutor(scheduler._registry, scheduler._policy, approvals),
        policy=scheduler._policy,
        approvals=approvals,
        attempts=attempts,
        retry=RetryEngine(RetryLimits(max_attempts=3)),
        evidence=RuntimeEvidenceWriter(EvidenceLedger(tmp_path / "repair-evidence.db")),
        tool_bindings={"mode.test.execute": "nexus.test.execute"},
    )
    original_digest = snapshot.graph.graph.digest
    result = asyncio.run(
        scheduler.tick(snapshot, actor_id="runtime-scheduler", trace_id=TRACE, now=NOW)
    )
    assert result.outcome is SchedulerOutcome.REPAIR_REQUIRED
    assert result.snapshot.graph.graph.digest == original_digest
    assert result.snapshot.task_states[TaskId("first_task")] is TaskStatus.READY


def test_repeated_failure_limit_stops_third_attempt(tmp_path) -> None:
    scheduler, snapshot, approvals, calls = _subject(tmp_path, max_attempts=5)
    attempts = AttemptStore(tmp_path / "repeat-attempts.db")

    async def handler(payload):
        calls.append(payload)
        raise OSError("same synthetic failure")

    scheduler._registry._handlers["nexus.test.execute"] = handler
    scheduler = GovernedScheduler(
        runtime=scheduler._runtime,
        registry=scheduler._registry,
        executor=ToolExecutor(scheduler._registry, scheduler._policy, approvals),
        policy=scheduler._policy,
        approvals=approvals,
        attempts=attempts,
        retry=RetryEngine(RetryLimits(max_attempts=5, max_repeated_failures=2)),
        evidence=RuntimeEvidenceWriter(EvidenceLedger(tmp_path / "repeat-evidence.db")),
        tool_bindings={"mode.test.execute": "nexus.test.execute"},
    )
    current = snapshot
    outcomes = []
    for _ in range(2):
        result = asyncio.run(
            scheduler.tick(current, actor_id="runtime-scheduler", trace_id=TRACE, now=NOW)
        )
        outcomes.append(result.outcome)
        current = result.snapshot
    assert outcomes == [SchedulerOutcome.RETRY_SCHEDULED, SchedulerOutcome.FAILED]
    assert len(attempts.history(snapshot.run_id, TaskId("first_task"))) == 2
