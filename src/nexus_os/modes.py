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
RESEARCH_VERSION: Final = "1.0"
DATA_ANALYSIS_VERSION: Final = "1.0"


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

_RESEARCH_STAGES = (
    _Stage("protocol", "mode.research.protocol", "protocol.json", 300, True),
    _Stage("source_acquisition", "mode.research.source_acquisition", "sources.json", 900, True),
    _Stage("source_extraction", "mode.research.source_extraction", "extractions.json", 900, False),
    _Stage("claim_construction", "mode.research.claim_construction", "claims.json", 600, True),
    _Stage("deterministic_compute", "mode.research.compute", "computations.json", 900, False),
    _Stage("synthesis", "mode.research.synthesis", "research-report-draft.md", 600, True),
    _Stage("conflict_review", "mode.research.conflict_review", "conflicts.json", 300, False),
    _Stage(
        "citation_verification", "mode.research.citation_verification", "citations.json", 600, False
    ),
    _Stage("reproducibility", "mode.research.reproducibility", "reproducibility.json", 900, False),
    _Stage("evidence_report", "mode.research.evidence", "evidence-report.json", 300, False),
)

_DATA_ANALYSIS_STAGES = (
    _Stage("ingestion", "mode.data_analysis.ingestion", "dataset.json", 900, False),
    _Stage("schema_inspection", "mode.data_analysis.schema", "schema.json", 300, False),
    _Stage("quality_check", "mode.data_analysis.quality", "data-quality.json", 600, False),
    _Stage("statistics", "mode.data_analysis.statistics", "statistics.json", 900, False),
    _Stage("chart_spec", "mode.data_analysis.chart_spec", "chart-spec.json", 300, False),
    _Stage("explanation", "mode.data_analysis.explanation", "explanation.md", 600, True),
    _Stage("persistence", "mode.data_analysis.persistence", "analysis-state.json", 600, False),
    _Stage("reopen_verify", "mode.data_analysis.reopen_verify", "reopen-check.json", 600, False),
    _Stage("evidence_report", "mode.data_analysis.evidence", "evidence-report.json", 300, False),
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


class ResearchMode:
    """Compile research questions into a provenance-first, non-publishing DAG."""

    def compile(self, config: LoadedConfig) -> ValidatedTaskGraph:
        if not isinstance(config, LoadedConfig):
            raise ModeCompileError("research requires a validated project configuration")
        data = config.data
        if data.get("mode") != "research":
            raise ModeCompileError("project mode must be research")
        workspace = _mapping(data.get("workspace"), "workspace")
        if workspace.get("read_only") is True:
            raise ModeCompileError("research requires a writable workspace")
        project_id = _string(data.get("project_id"), "project_id")
        question = _string(data.get("goal"), "goal")
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
        for stage in _RESEARCH_STAGES:
            task_id = TaskId(stage.task_id)
            task_input = _research_input(stage, question, acceptance)
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
        graph_id = uuid5(NAMESPACE_URL, f"nexus:research:{RESEARCH_VERSION}:{config.digest}")
        return validate_task_graph(TaskGraph(graph_id, project_id, tuple(tasks)))


class DataAnalysisMode:
    """Compile analysis goals into deterministic, artifact-grounded work."""

    def compile(self, config: LoadedConfig) -> ValidatedTaskGraph:
        if not isinstance(config, LoadedConfig):
            raise ModeCompileError("data_analysis requires a validated project configuration")
        data = config.data
        if data.get("mode") != "data_analysis":
            raise ModeCompileError("project mode must be data_analysis")
        workspace = _mapping(data.get("workspace"), "workspace")
        if workspace.get("read_only") is True:
            raise ModeCompileError("data_analysis requires a writable workspace")
        project_id = _string(data.get("project_id"), "project_id")
        goal = _string(data.get("goal"), "goal")
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
        for stage in _DATA_ANALYSIS_STAGES:
            task_id = TaskId(stage.task_id)
            task_input = _analysis_input(stage, goal, acceptance)
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
        graph_id = uuid5(
            NAMESPACE_URL, f"nexus:data_analysis:{DATA_ANALYSIS_VERSION}:{config.digest}"
        )
        return validate_task_graph(TaskGraph(graph_id, project_id, tuple(tasks)))


def _research_input(
    stage: _Stage, question: str, acceptance: tuple[dict[str, str], ...]
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "mode_version": RESEARCH_VERSION,
        "expected_artifact": stage.artifact,
    }
    if stage.task_id == "protocol":
        value.update(
            question=question,
            required_data_controls=(
                "classification",
                "minimized_access",
                "provider_routing",
                "egress_approval",
            ),
        )
    elif stage.task_id == "source_acquisition":
        value.update(
            network_access="policy_scoped",
            required_source_fields=(
                "locator",
                "retrieved_at",
                "content_digest",
                "license_access",
                "extractor_version",
                "provenance",
            ),
        )
    elif stage.task_id == "claim_construction":
        value.update(
            required_claim_links=("source_spans", "deterministic_artifacts"),
            allowed_derivations=("direct", "calculated", "inferred"),
        )
    elif stage.task_id == "deterministic_compute":
        value["required_provenance"] = (
            "engine",
            "version",
            "parameters",
            "environment",
            "seed",
            "input_digest",
            "output_digest",
            "reproducibility_status",
        )
    elif stage.task_id == "synthesis":
        value.update(
            numeric_claims_require_artifacts=True,
            external_publication=False,
        )
    elif stage.task_id == "conflict_review":
        value.update(retain_contradictions=True, report_unresolved_conflicts=True)
    elif stage.task_id == "citation_verification":
        value.update(
            deterministic_checks=("citation_exists", "source_span_exists", "artifact_value_matches")
        )
    elif stage.task_id == "reproducibility":
        value.update(require_explicit_limitations=True, require_reproducible_artifacts=True)
    elif stage.task_id == "evidence_report":
        value["acceptance"] = acceptance
    return value


def _analysis_input(
    stage: _Stage, goal: str, acceptance: tuple[dict[str, str], ...]
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "mode_version": DATA_ANALYSIS_VERSION,
        "expected_artifact": stage.artifact,
    }
    if stage.task_id == "ingestion":
        value.update(
            goal=goal,
            model_generated_numbers_allowed=False,
            required_provenance=("input_digest", "row_count", "column_count", "format"),
        )
    elif stage.task_id == "schema_inspection":
        value["deterministic_checks"] = ("column_names", "types", "nullability", "row_width")
    elif stage.task_id == "quality_check":
        value.update(
            deterministic_findings=True,
            required_checks=("missing", "duplicates", "type_violations", "non_finite"),
        )
    elif stage.task_id == "statistics":
        value["required_provenance"] = (
            "engine", "version", "parameters", "seed", "input_digest", "output_digest"
        )
    elif stage.task_id == "chart_spec":
        value.update(require_computed_columns=True, validate_specification=True)
    elif stage.task_id == "explanation":
        value.update(
            numeric_claims_require_artifact_ids=True,
            unverified_numbers_allowed=False,
        )
    elif stage.task_id == "persistence":
        value["required_state"] = ("dataset_digest", "analysis_artifacts", "graph_digest")
    elif stage.task_id == "reopen_verify":
        value["deterministic_checks"] = (
            "dataset_digest_matches", "artifacts_match", "state_is_compatible"
        )
    elif stage.task_id == "evidence_report":
        value["acceptance"] = acceptance
    return value


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
