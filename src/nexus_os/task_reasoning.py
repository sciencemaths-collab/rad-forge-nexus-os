"""Qualified, proposal-only reasoning for one approved runtime task."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from nexus_os.domain import ActionEffect, RunId, TaskDefinition, TaskStatus, TraceId
from nexus_os.model_qualification import ModelUse
from nexus_os.model_registry import ModelRegistryError
from nexus_os.providers import AgentAdapter, ProviderTask
from nexus_os.secrets import redact

_OUTPUT_LIMIT = 64_000
_PROMPT_LIMIT = 64_000
_FIELDS = {
    "schema_version",
    "title",
    "summary",
    "sections",
    "evidence_notes",
    "unresolved_questions",
}
_SYSTEM = (
    "Return one JSON object only for the approved task. Propose bounded artifact content; "
    "do not call tools, execute actions, claim success, alter the task, include credentials, "
    "or add fields. Deterministic code will validate and decide whether anything is written."
)


class TaskReasoningError(ValueError):
    """Safe qualification, provider, or structured-output failure."""


class TaskModelUseAuthorizer(Protocol):
    def authorize(
        self,
        *,
        provider_id: str,
        model_id: str,
        adapter_version: str,
        use: ModelUse,
        at: datetime,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class ReasonedTaskArtifact:
    title: str
    summary: str
    sections: tuple[tuple[str, str], ...]
    evidence_notes: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if (
            self.schema_version != "1.0"
            or not self.sections
            or len(self.sections) > 32
            or len(self.evidence_notes) > 32
            or len(self.unresolved_questions) > 32
        ):
            raise TaskReasoningError("reasoned task artifact is invalid")
        _text(self.title, 200)
        _text(self.summary, 4000)
        for heading, content in self.sections:
            _text(heading, 200)
            _text(content, 8000)
        for item in self.evidence_notes:
            _text(item, 1000)
        for item in self.unresolved_questions:
            _text(item, 2000)
        if redact(self.to_dict()) != self.to_dict():
            raise TaskReasoningError("reasoned task artifact contains secret-like material")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "title": self.title,
            "summary": self.summary,
            "sections": [
                {"heading": heading, "content": content} for heading, content in self.sections
            ],
            "evidence_notes": list(self.evidence_notes),
            "unresolved_questions": list(self.unresolved_questions),
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        return "sha256:" + hashlib.sha256(encoded).hexdigest()


class QualifiedTaskReasoner:
    """Ask an exactly qualified model for data; never dispatch a tool or persist output."""

    def __init__(
        self,
        *,
        qualifications: TaskModelUseAuthorizer,
        adapter: AgentAdapter,
        provider_id: str,
        model_id: str,
        adapter_version: str,
        timeout_seconds: int = 60,
    ) -> None:
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 600
        ):
            raise TaskReasoningError("task reasoning timeout is invalid")
        self._qualifications = qualifications
        self._adapter = adapter
        self._provider_id = provider_id
        self._model_id = model_id
        self._adapter_version = adapter_version
        self._timeout = timeout_seconds

    async def propose(
        self,
        task: TaskDefinition,
        *,
        run_id: RunId,
        trace_id: TraceId,
        at: datetime,
        allow_repair: bool = True,
    ) -> ReasonedTaskArtifact:
        _utc(at)
        use = (
            ModelUse.SENSITIVE_ACTION_PROPOSAL
            if task.effect in {ActionEffect.SENSITIVE, ActionEffect.DESTRUCTIVE}
            else ModelUse.TASK_PLANNING
        )
        self._authorize(use, at)
        output = await self._call(task, run_id, trace_id, repair=False)
        try:
            return _artifact(output)
        except TaskReasoningError:
            if not allow_repair:
                raise
            self._authorize(ModelUse.REPAIR_PROPOSAL, at)
            return _artifact(await self._call(task, run_id, trace_id, repair=True))

    def _authorize(self, use: ModelUse, at: datetime) -> None:
        try:
            self._qualifications.authorize(
                provider_id=self._provider_id,
                model_id=self._model_id,
                adapter_version=self._adapter_version,
                use=use,
                at=at,
            )
        except ModelRegistryError as exc:
            raise TaskReasoningError("exact model qualification does not permit task use") from exc

    async def _call(
        self,
        task: TaskDefinition,
        run_id: RunId,
        trace_id: TraceId,
        *,
        repair: bool,
    ) -> str:
        task_document = task.canonical_dict()
        if redact(task_document) != task_document:
            raise TaskReasoningError("approved task input contains secret-like material")
        prompt = "Approved task:\n" + json.dumps(
            task_document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        prompt += (
            "\nPrevious response failed validation. Return a corrected object."
            if repair
            else "\nPropose the structured artifact object."
        )
        if len(prompt.encode()) > _PROMPT_LIMIT:
            raise TaskReasoningError("approved task prompt exceeds the reasoning limit")
        provider_task = ProviderTask(
            f"reason:{run_id!s}:{task.task_id}:{'repair' if repair else 'draft'}",
            run_id,
            task.task_id,
            trace_id,
            "task_planning",
            {"system": _SYSTEM, "prompt": prompt},
            self._timeout,
        )
        try:
            key = await self._adapter.run(provider_task)
            result = await self._adapter.result(key)
        except Exception as exc:
            raise TaskReasoningError("task reasoning provider request failed safely") from exc
        output = result.metadata.get("output_text")
        if (
            result.status is not TaskStatus.SUCCEEDED
            or not isinstance(output, str)
            or not 1 <= len(output.encode()) <= _OUTPUT_LIMIT
        ):
            raise TaskReasoningError("task reasoning provider returned no bounded proposal")
        return output


def _artifact(output: str) -> ReasonedTaskArtifact:
    try:
        value = json.loads(
            output,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
            object_pairs_hook=_unique_object,
        )
        if (
            not isinstance(value, dict)
            or set(value) != _FIELDS
            or value.get("schema_version") != "1.0"
            or redact(value) != value
        ):
            raise ValueError
        title = _text(value.get("title"), 200)
        summary = _text(value.get("summary"), 4000)
        raw_sections = value.get("sections")
        if not isinstance(raw_sections, list) or not 1 <= len(raw_sections) <= 32:
            raise ValueError
        sections: list[tuple[str, str]] = []
        for raw in raw_sections:
            if not isinstance(raw, Mapping) or set(raw) != {"heading", "content"}:
                raise ValueError
            sections.append((_text(raw["heading"], 200), _text(raw["content"], 8000)))
        evidence = _texts(value.get("evidence_notes"), 32, 1000)
        questions = _texts(value.get("unresolved_questions"), 32, 2000)
        return ReasonedTaskArtifact(title, summary, tuple(sections), evidence, questions)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TaskReasoningError("model task proposal failed strict validation") from exc


def _texts(value: object, maximum_items: int, maximum_length: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum_items:
        raise ValueError
    return tuple(_text(item, maximum_length) for item in value)


def _text(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError
        value[key] = item
    return value


def _utc(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise TaskReasoningError("task reasoning time must be timezone-aware UTC")
