"""Proposal-only conversational reasoning controller for NEXUS Agent."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

from nexus_os.agent_store import (
    AgentSession,
    AgentSessionStore,
    AgentState,
    CandidateSpecification,
    candidate_digest,
)
from nexus_os.domain import RunId, TaskId, TaskStatus, TraceId
from nexus_os.model_qualification import ModelUse
from nexus_os.model_registry import ModelRegistryError
from nexus_os.providers import AgentAdapter, ProviderTask
from nexus_os.secrets import redact

_OUTPUT_LIMIT = 64_000
_PROPOSAL_FIELDS = {
    "objective",
    "mode",
    "inputs",
    "constraints",
    "acceptance_criteria",
    "required_capabilities",
    "risk_summary",
    "unresolved_questions",
    "review_ready",
}
_SYSTEM = (
    "Return one JSON object only. Produce a candidate specification, never execute work, "
    "never claim approval or completion, never include credentials, and never add fields."
)


class AgentControllerError(ValueError):
    """Safe controlled-inference or proposal-validation failure."""


class ModelUseAuthorizer(Protocol):
    def authorize(
        self,
        *,
        provider_id: str,
        model_id: str,
        adapter_version: str,
        use: ModelUse,
        at: datetime,
    ) -> object: ...


class IdFactory(Protocol):
    def candidate_id(self) -> UUID: ...
    def event_id(self) -> UUID: ...


class AgentReasoningController:
    def __init__(
        self,
        *,
        sessions: AgentSessionStore,
        qualifications: ModelUseAuthorizer,
        adapter: AgentAdapter,
        provider_id: str,
        model_id: str,
        adapter_version: str,
        ids: IdFactory,
        timeout_seconds: int = 60,
    ) -> None:
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 600
        ):
            raise AgentControllerError("controller timeout is invalid")
        self._sessions = sessions
        self._qualifications = qualifications
        self._adapter = adapter
        self._provider_id = provider_id
        self._model_id = model_id
        self._adapter_version = adapter_version
        self._ids = ids
        self._timeout = timeout_seconds

    async def prepare(
        self,
        session_id: UUID,
        *,
        actor_id: str,
        at: datetime,
        expected_sequence: int,
        trace_id: TraceId,
        allow_repair: bool = True,
        clarification: str | None = None,
    ) -> AgentSession:
        _utc(at)
        if clarification is not None and (
            not isinstance(clarification, str)
            or not 1 <= len(clarification) <= 8000
            or redact(clarification) != clarification
        ):
            raise AgentControllerError(
                "clarification context is invalid or secret-like"
            )
        session = self._sessions.get(session_id)
        if (
            session.state is not AgentState.DRAFTING
            or len(session.events) != expected_sequence
        ):
            raise AgentControllerError(
                "session is not at the expected drafting revision"
            )
        self._authorize(ModelUse.CANDIDATE_SPECIFICATION, at)
        objective = self._sessions.objective(session_id)
        revision = self._next_revision(session_id)
        output = await self._call(
            session_id,
            trace_id,
            objective,
            revision,
            repair=False,
            clarification=clarification,
        )
        try:
            candidate = self._candidate(output, session_id, revision)
        except AgentControllerError:
            if not allow_repair:
                raise
            self._authorize(ModelUse.REPAIR_PROPOSAL, at)
            output = await self._call(
                session_id,
                trace_id,
                objective,
                revision,
                repair=True,
                clarification=clarification,
            )
            candidate = self._candidate(output, session_id, revision)
        return self._sessions.save_candidate(
            candidate,
            event_id=self._ids.event_id(),
            actor_id=actor_id,
            occurred_at=at,
            expected_sequence=expected_sequence,
        )

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
            raise AgentControllerError(
                "exact model qualification does not permit controller use"
            ) from exc

    def _next_revision(self, session_id: UUID) -> int:
        try:
            return self._sessions.get_candidate(session_id).revision + 1
        except ValueError:
            return 1

    async def _call(
        self,
        session_id: UUID,
        trace_id: TraceId,
        objective: str,
        revision: int,
        *,
        repair: bool,
        clarification: str | None,
    ) -> str:
        prompt = f"Objective:\n{objective}\nRevision: {revision}\n"
        if clarification is not None:
            prompt += f"User clarification:\n{clarification}\n"
        prompt += (
            "Previous response failed schema validation. Return a corrected object."
            if repair
            else "Create the candidate object."
        )
        task = ProviderTask(
            f"agent-{session_id.hex[:16]}-r{revision}-{'repair' if repair else 'draft'}",
            RunId.parse(session_id),
            TaskId("agent_candidate"),
            trace_id,
            "candidate_specification",
            {"system": _SYSTEM, "prompt": prompt},
            self._timeout,
        )
        try:
            key = await self._adapter.run(task)
            result = await self._adapter.result(key)
        except Exception as exc:
            raise AgentControllerError(
                "reasoning provider request failed safely"
            ) from exc
        output = result.metadata.get("output_text")
        if (
            result.status is not TaskStatus.SUCCEEDED
            or not isinstance(output, str)
            or not 1 <= len(output.encode()) <= _OUTPUT_LIMIT
        ):
            raise AgentControllerError(
                "reasoning provider did not return a complete bounded proposal"
            )
        return output

    def _candidate(
        self, output: str, session_id: UUID, revision: int
    ) -> CandidateSpecification:
        try:
            value = json.loads(
                output,
                parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
                object_pairs_hook=_unique_object,
            )
            if (
                not isinstance(value, dict)
                or set(value) != _PROPOSAL_FIELDS
                or redact(value) != value
            ):
                raise ValueError
            unsigned: dict[str, Any] = {
                "schema_version": "1.0",
                "candidate_id": str(self._candidate_id(session_id)),
                "session_id": str(session_id),
                "revision": revision,
                **cast(Mapping[str, Any], value),
            }
            document = {**unsigned, "candidate_digest": candidate_digest(unsigned)}
            return CandidateSpecification.parse(document)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AgentControllerError(
                "model proposal failed strict candidate validation"
            ) from exc

    def _candidate_id(self, session_id: UUID) -> UUID:
        try:
            existing = self._sessions.get_candidate(session_id)
            return existing.candidate_id
        except ValueError:
            return self._ids.candidate_id()


def _utc(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise AgentControllerError("controller time must be timezone-aware UTC")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value
