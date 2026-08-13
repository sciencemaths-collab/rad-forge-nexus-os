"""One-tick governed scheduler joining runtime, policy, approval, and typed tools."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from uuid import NAMESPACE_URL, UUID, uuid5

from nexus_os.approval import ApprovalError, ApprovalRecord, ApprovalStatus, ApprovalStore
from nexus_os.domain import (
    Failure,
    FailureClass,
    TaskDefinition,
    TaskId,
    TaskStatus,
    TraceId,
)
from nexus_os.policy import (
    ActionRequest,
    DataClass,
    Environment,
    PolicyDecision,
    PolicyDecisionKind,
    PolicyEngine,
)
from nexus_os.runtime import RuntimeOrchestrator, RuntimeSnapshot
from nexus_os.tools import ToolError, ToolExecutor, ToolRegistry, ToolResult


class SchedulerError(ValueError):
    """Safe scheduler validation, binding, or lifecycle failure."""


class SchedulerOutcome(StrEnum):
    IDLE = "IDLE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class SchedulerTickResult:
    outcome: SchedulerOutcome
    snapshot: RuntimeSnapshot
    task_id: TaskId | None = None
    approval: ApprovalRecord | None = None
    tool_result: ToolResult | None = None
    failure: Failure | None = None


class GovernedScheduler:
    """Select and finish at most one task; never bypass policy or typed tools."""

    def __init__(
        self,
        *,
        runtime: RuntimeOrchestrator,
        registry: ToolRegistry,
        executor: ToolExecutor,
        policy: PolicyEngine,
        approvals: ApprovalStore,
        tool_bindings: Mapping[str, str],
        approval_ttl: timedelta = timedelta(hours=1),
    ) -> None:
        if not timedelta(seconds=1) <= approval_ttl <= timedelta(days=7):
            raise SchedulerError("approval_ttl must be from one second to seven days")
        bindings = dict(tool_bindings)
        if not bindings or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in bindings.items()
        ):
            raise SchedulerError("tool bindings must be a non-empty string mapping")
        for name in bindings.values():
            registry.get(name)
        self._runtime = runtime
        self._registry = registry
        self._executor = executor
        self._policy = policy
        self._approvals = approvals
        self._bindings = MappingProxyType(bindings)
        self._approval_ttl = approval_ttl

    async def tick(
        self,
        snapshot: RuntimeSnapshot,
        *,
        actor_id: str,
        trace_id: TraceId,
        now: datetime,
        approval_id: UUID | None = None,
        task_id: TaskId | None = None,
    ) -> SchedulerTickResult:
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise SchedulerError("now must be timezone-aware UTC")
        task = self._select(snapshot, approval_id=approval_id, task_id=task_id)
        if task is None:
            return SchedulerTickResult(SchedulerOutcome.IDLE, snapshot)
        tool_name = self._bindings.get(task.kind)
        if tool_name is None:
            return self._fail(
                snapshot,
                task,
                trace_id,
                now,
                "tool.binding_missing",
                "Task tool binding is missing.",
                FailureClass.MISSING_DEPENDENCY,
            )
        descriptor = self._registry.get(tool_name)
        if descriptor.effect is not task.effect:
            return self._fail(
                snapshot,
                task,
                trace_id,
                now,
                "tool.effect_mismatch",
                "Task and tool effects do not match.",
                FailureClass.SECURITY_POLICY,
            )
        decision = self._decision(actor_id, snapshot, task, tool_name)
        if decision.kind is PolicyDecisionKind.DENY:
            return self._fail(
                snapshot,
                task,
                trace_id,
                now,
                "policy.denied",
                "Task dispatch was denied by policy.",
                FailureClass.SECURITY_POLICY,
            )
        needs_approval = (
            descriptor.approval_required or decision.kind is PolicyDecisionKind.REQUIRE_APPROVAL
        )
        if needs_approval and approval_id is None:
            if task.effect.value not in {"SENSITIVE", "DESTRUCTIVE"}:
                return self._fail(
                    snapshot,
                    task,
                    trace_id,
                    now,
                    "approval.effect_invalid",
                    "Approval-required tool effect is invalid.",
                    FailureClass.SECURITY_POLICY,
                )
            approval = self._approval(snapshot, task, decision, actor_id, now)
            waiting = self._runtime.wait_for_approval(
                snapshot, task.task_id, trace_id=trace_id, now=now
            )
            return SchedulerTickResult(
                SchedulerOutcome.APPROVAL_REQUIRED, waiting, task.task_id, approval
            )
        if task_status(snapshot, task.task_id) is TaskStatus.WAITING_APPROVAL:
            if approval_id is None:
                return SchedulerTickResult(SchedulerOutcome.IDLE, snapshot)
            self._preflight_approval(approval_id, snapshot, decision, now)
            snapshot = self._runtime.release_approval(
                snapshot, task.task_id, trace_id=trace_id, now=now
            )
        running = self._runtime.start_task(snapshot, task.task_id, trace_id=trace_id, now=now)
        try:
            result = await self._executor.execute(
                tool_name,
                task.input,
                actor_id=actor_id,
                project_id=snapshot.graph.graph.project_id,
                run_id=snapshot.run_id,
                approval_id=approval_id,
                now=now,
            )
        except ToolError:
            failure = Failure(
                FailureClass.CONTRACT_MISMATCH,
                "tool.execution_failed",
                "Typed tool execution failed.",
                False,
            )
            failed = self._runtime.complete_task(
                running,
                task.task_id,
                TaskStatus.FAILED,
                trace_id=trace_id,
                now=now,
                failure=failure,
            )
            return SchedulerTickResult(
                SchedulerOutcome.FAILED, failed, task.task_id, failure=failure
            )
        completed = self._runtime.complete_task(
            running, task.task_id, TaskStatus.SUCCEEDED, trace_id=trace_id, now=now
        )
        return SchedulerTickResult(
            SchedulerOutcome.SUCCEEDED, completed, task.task_id, tool_result=result
        )

    def _select(
        self, snapshot: RuntimeSnapshot, *, approval_id: UUID | None, task_id: TaskId | None
    ) -> TaskDefinition | None:
        tasks = {item.task_id: item for item in snapshot.graph.graph.tasks}
        if task_id is not None:
            if task_id not in tasks or task_status(snapshot, task_id) not in {
                TaskStatus.READY,
                TaskStatus.WAITING_APPROVAL,
            }:
                raise SchedulerError("selected task is not schedulable")
            return tasks[task_id]
        target = TaskStatus.WAITING_APPROVAL if approval_id is not None else TaskStatus.READY
        for candidate in snapshot.graph.topological_order:
            if task_status(snapshot, candidate) is target:
                return tasks[candidate]
        return None

    def _decision(
        self, actor_id: str, snapshot: RuntimeSnapshot, task: TaskDefinition, tool_name: str
    ) -> PolicyDecision:
        return self._policy.evaluate(
            ActionRequest(
                actor_id=actor_id,
                project_id=snapshot.graph.graph.project_id,
                operation=tool_name,
                effect=task.effect,
                environment=Environment.LOCAL,
                data_class=DataClass.INTERNAL,
                estimated_cost=0.0,
            )
        )

    def _approval(
        self,
        snapshot: RuntimeSnapshot,
        task: TaskDefinition,
        decision: PolicyDecision,
        actor_id: str,
        now: datetime,
    ) -> ApprovalRecord:
        approval_id = uuid5(
            NAMESPACE_URL,
            f"nexus:approval:{snapshot.run_id}:{task.task_id}:{decision.action_digest}",
        )
        try:
            return self._approvals.get(approval_id)
        except ApprovalError:
            return self._approvals.request(
                approval_id=approval_id,
                project_id=snapshot.graph.graph.project_id,
                run_id=snapshot.run_id,
                action_digest=decision.action_digest,
                effect=task.effect,
                requested_by=actor_id,
                requested_at=now,
                expires_at=now + self._approval_ttl,
            )

    def _preflight_approval(
        self, approval_id: UUID, snapshot: RuntimeSnapshot, decision: PolicyDecision, now: datetime
    ) -> None:
        try:
            record = self._approvals.get(approval_id)
        except ApprovalError as exc:
            raise SchedulerError("approval is unavailable") from exc
        if (
            record.status is not ApprovalStatus.APPROVED
            or now >= record.expires_at
            or record.project_id != snapshot.graph.graph.project_id
            or record.run_id != snapshot.run_id
            or record.action_digest != decision.action_digest
        ):
            raise SchedulerError("approval is not valid for this task action")

    def _fail(
        self,
        snapshot: RuntimeSnapshot,
        task: TaskDefinition,
        trace_id: TraceId,
        now: datetime,
        code: str,
        message: str,
        classification: FailureClass,
    ) -> SchedulerTickResult:
        running = self._runtime.start_task(snapshot, task.task_id, trace_id=trace_id, now=now)
        failure = Failure(classification, code, message, False)
        failed = self._runtime.complete_task(
            running, task.task_id, TaskStatus.FAILED, trace_id=trace_id, now=now, failure=failure
        )
        return SchedulerTickResult(SchedulerOutcome.FAILED, failed, task.task_id, failure=failure)


def task_status(snapshot: RuntimeSnapshot, task_id: TaskId) -> TaskStatus:
    try:
        return snapshot.task_states[task_id]
    except KeyError as exc:
        raise SchedulerError("task is not present in runtime snapshot") from exc
