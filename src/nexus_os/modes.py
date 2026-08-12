"""Mode packs compile validated projects into shared kernel task contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast
from uuid import NAMESPACE_URL, uuid5

from nexus_os.config import LoadedConfig
from nexus_os.domain import ActionEffect, TaskDefinition, TaskGraph, TaskId
from nexus_os.graph import ValidatedTaskGraph, validate_task_graph

APP_BUILD_VERSION: Final = "1.0"


class ModeCompileError(ValueError):
    """Safe rejection of a project that cannot compile for the selected mode."""


@dataclass(frozen=True, slots=True)
class _Stage:
    task_id: str
    kind: str
    artifact: str
    timeout_seconds: int
    retryable: bool


_APP_BUILD_STAGES = (
    _Stage("specification", "mode.app_build.specification", "specification.md", 300, True),
    _Stage("design", "mode.app_build.design", "architecture.md", 300, True),
    _Stage("contract_test", "mode.app_build.contract_test", "contract-tests.json", 300, False),
    _Stage("implementation", "mode.app_build.implementation", "implementation", 900, True),
    _Stage("unit_test", "mode.app_build.unit_test", "unit-tests.json", 600, False),
    _Stage(
        "integration_test", "mode.app_build.integration_test", "integration-tests.json", 900, False
    ),
    _Stage("security_test", "mode.app_build.security_test", "security-tests.json", 900, False),
    _Stage("failure_test", "mode.app_build.failure_test", "failure-tests.json", 900, False),
    _Stage("evidence_report", "mode.app_build.evidence", "evidence-report.json", 300, False),
)


class AppBuildMode:
    """Compile app requirements into an auditable, fail-fast engineering DAG."""

    def compile(self, config: LoadedConfig) -> ValidatedTaskGraph:
        if not isinstance(config, LoadedConfig):
            raise ModeCompileError("app_build requires a validated project configuration")
        data = config.data
        if data.get("mode") != "app_build":
            raise ModeCompileError("project mode must be app_build")
        workspace = _mapping(data.get("workspace"), "workspace")
        if workspace.get("read_only") is True:
            raise ModeCompileError("app_build requires a writable workspace")
        project_id = _string(data.get("project_id"), "project_id")
        goal = _string(data.get("goal"), "goal")
        name = _string(data.get("name"), "name")
        policy = _mapping(data.get("policy"), "policy")
        max_attempts = policy.get("max_attempts")
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool):
            raise ModeCompileError("project retry policy is invalid")
        acceptance = _acceptance(data.get("acceptance"))
        acceptance_ids = tuple(item["id"] for item in acceptance)
        if len(set(acceptance_ids)) != len(acceptance_ids):
            raise ModeCompileError("acceptance identifiers must be unique")

        tasks: list[TaskDefinition] = []
        previous: TaskId | None = None
        for stage in _APP_BUILD_STAGES:
            task_id = TaskId(stage.task_id)
            task_input: dict[str, Any] = {
                "mode_version": APP_BUILD_VERSION,
                "expected_artifact": stage.artifact,
            }
            if stage.task_id == "specification":
                task_input.update(project_name=name, goal=goal)
            if stage.task_id in {"contract_test", "evidence_report"}:
                task_input["acceptance"] = acceptance
            tasks.append(
                TaskDefinition(
                    task_id=task_id,
                    kind=stage.kind,
                    depends_on=() if previous is None else (previous,),
                    effect=ActionEffect.WORKSPACE_WRITE,
                    timeout_seconds=stage.timeout_seconds,
                    max_attempts=max_attempts if stage.retryable else 1,
                    backoff_seconds=1.0 if stage.retryable else 0.0,
                    input=task_input,
                    acceptance_ids=acceptance_ids if stage.task_id == "evidence_report" else (),
                )
            )
            previous = task_id
        graph_id = uuid5(NAMESPACE_URL, f"nexus:app_build:{APP_BUILD_VERSION}:{config.digest}")
        return validate_task_graph(TaskGraph(graph_id, project_id, tuple(tasks)))


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ModeCompileError(f"{name} must be an object")
    return cast(Mapping[str, Any], value)


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ModeCompileError(f"{name} must be a non-empty string")
    return value


def _acceptance(value: object) -> tuple[dict[str, str], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ModeCompileError("acceptance must be an array")
    result: list[dict[str, str]] = []
    for item in value:
        mapping = _mapping(item, "acceptance item")
        result.append(
            {
                "id": _string(mapping.get("id"), "acceptance id"),
                "description": _string(mapping.get("description"), "acceptance description"),
                "verifier": _string(mapping.get("verifier"), "acceptance verifier"),
            }
        )
    if not result:
        raise ModeCompileError("acceptance must not be empty")
    return tuple(result)
