import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from nexus_os.approval import ApprovalStatus, ApprovalStore
from nexus_os.domain import ActionEffect, RunId, TaskId, TaskStatus, TraceId
from nexus_os.graph import compile_task_graph, validate_task_graph
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.runtime import RuntimeOrchestrator
from nexus_os.scheduler import GovernedScheduler, SchedulerError, SchedulerOutcome
from nexus_os.stores import SQLiteCheckpointStore
from nexus_os.tools import ToolDescriptor, ToolExecutor, ToolRegistry

NOW = datetime(2026, 8, 13, 21, tzinfo=UTC)
TRACE = TraceId("abcdef1234567890abcdef1234567890")


def _graph(effect: ActionEffect = ActionEffect.READ_ONLY):
    return validate_task_graph(
        compile_task_graph(
            {
                "schema_version": "1.0",
                "graph_id": "82000000-0000-4000-8000-000000000001",
                "project_id": "scheduler-test",
                "tasks": [
                    {
                        "task_id": "first_task",
                        "kind": "mode.test.execute",
                        "depends_on": [],
                        "effect": effect.value,
                        "timeout_seconds": 30,
                        "retry": {"max_attempts": 1, "backoff_seconds": 0},
                        "input": {
                            "value": "approved input",
                            "idempotency_key": "scheduler-test-0001",
                        },
                    }
                ],
            }
        )
    )


def _registry(effect: ActionEffect, calls: list[dict[str, Any]]) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            "nexus.test.execute",
            "Execute one scheduler contract task.",
            effect,
            1.0,
            True,
            effect in {ActionEffect.SENSITIVE, ActionEffect.DESTRUCTIVE},
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["value", "idempotency_key"],
                "properties": {
                    "value": {"type": "string"},
                    "idempotency_key": {"type": "string", "minLength": 16},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["accepted"],
                "properties": {"accepted": {"type": "boolean"}},
            },
        )
    )

    async def handler(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return {"accepted": True}

    registry.bind("nexus.test.execute", handler)
    return registry


def _subject(tmp_path, effect=ActionEffect.READ_ONLY, rules=None):
    calls: list[dict[str, Any]] = []
    store = SQLiteCheckpointStore(tmp_path / "runtime.db")
    runtime = RuntimeOrchestrator(store)
    approvals = ApprovalStore(tmp_path / "approvals.db")
    policy = PolicyEngine(rules or PolicyRules())
    registry = _registry(effect, calls)
    scheduler = GovernedScheduler(
        runtime=runtime,
        registry=registry,
        executor=ToolExecutor(registry, policy, approvals),
        policy=policy,
        approvals=approvals,
        tool_bindings={"mode.test.execute": "nexus.test.execute"},
    )
    snapshot = runtime.create(
        run_id=RunId.parse("82000000-0000-4000-8000-000000000002"),
        graph=_graph(effect),
        trace_id=TRACE,
        now=NOW,
    )
    return scheduler, snapshot, approvals, calls


def test_allowed_tick_leases_executes_and_completes_one_task(tmp_path) -> None:
    scheduler, snapshot, _, calls = _subject(tmp_path)
    result = asyncio.run(
        scheduler.tick(snapshot, actor_id="runtime-scheduler", trace_id=TRACE, now=NOW)
    )
    assert result.outcome is SchedulerOutcome.SUCCEEDED
    assert result.snapshot.task_states[TaskId("first_task")] is TaskStatus.SUCCEEDED
    assert len(calls) == 1


def test_sensitive_task_waits_for_exact_human_approval_then_executes(tmp_path) -> None:
    scheduler, snapshot, approvals, calls = _subject(tmp_path, ActionEffect.SENSITIVE)
    waiting = asyncio.run(
        scheduler.tick(snapshot, actor_id="runtime-scheduler", trace_id=TRACE, now=NOW)
    )
    assert waiting.outcome is SchedulerOutcome.APPROVAL_REQUIRED
    assert waiting.snapshot.task_states[TaskId("first_task")] is TaskStatus.WAITING_APPROVAL
    assert calls == []
    assert waiting.approval is not None
    approved = approvals.decide(
        waiting.approval.approval_id,
        status=ApprovalStatus.APPROVED,
        decided_by="owner-reviewer",
        decided_at=NOW,
    )
    completed = asyncio.run(
        scheduler.tick(
            waiting.snapshot,
            actor_id="runtime-scheduler",
            trace_id=TRACE,
            now=NOW,
            approval_id=approved.approval_id,
        )
    )
    assert completed.outcome is SchedulerOutcome.SUCCEEDED
    assert approvals.get(approved.approval_id).status is ApprovalStatus.CONSUMED
    assert len(calls) == 1


def test_wrong_approval_cannot_mutate_waiting_task_or_call_handler(tmp_path) -> None:
    scheduler, snapshot, _, calls = _subject(tmp_path, ActionEffect.SENSITIVE)
    waiting = asyncio.run(
        scheduler.tick(snapshot, actor_id="runtime-scheduler", trace_id=TRACE, now=NOW)
    )
    with pytest.raises(SchedulerError, match="unavailable"):
        asyncio.run(
            scheduler.tick(
                waiting.snapshot,
                actor_id="runtime-scheduler",
                trace_id=TRACE,
                now=NOW,
                approval_id=UUID("82000000-0000-4000-8000-000000000099"),
            )
        )
    assert waiting.snapshot.task_states[TaskId("first_task")] is TaskStatus.WAITING_APPROVAL
    assert calls == []


def test_policy_denial_is_durable_failure_without_tool_call(tmp_path) -> None:
    rules = PolicyRules(denied_operations=frozenset({"nexus.test.execute"}))
    scheduler, snapshot, _, calls = _subject(tmp_path, rules=rules)
    result = asyncio.run(
        scheduler.tick(snapshot, actor_id="runtime-scheduler", trace_id=TRACE, now=NOW)
    )
    assert result.outcome is SchedulerOutcome.FAILED
    assert result.failure is not None and result.failure.code == "policy.denied"
    assert calls == []
