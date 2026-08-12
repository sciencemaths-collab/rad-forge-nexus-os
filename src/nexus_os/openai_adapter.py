"""OpenAI Responses adapter behind an injected vendor transport."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from nexus_os.domain import Failure, FailureClass, TaskStatus
from nexus_os.providers import (
    AdapterError,
    ConformanceLevel,
    HealthState,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderEvent,
    ProviderEventKind,
    ProviderResult,
    ProviderTask,
    Usage,
)
from nexus_os.secrets import SecretReference, SecretResolver, secret_scope

_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RESPONSE_ID = re.compile(r"^resp_[A-Za-z0-9_-]{1,120}$")
_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


class TransportError(RuntimeError):
    """Vendor-transport failure; its raw text never crosses the adapter boundary."""


class OpenAITransport(Protocol):
    async def health(self, api_key: str) -> bool: ...

    async def create(self, request: Mapping[str, object], api_key: str) -> Mapping[str, Any]: ...

    async def retrieve(self, response_id: str, api_key: str) -> Mapping[str, Any]: ...

    async def cancel_response(self, response_id: str, api_key: str) -> Mapping[str, Any]: ...


@dataclass(slots=True)
class _Execution:
    task: ProviderTask
    response_id: str
    events: list[ProviderEvent]
    result: ProviderResult | None


class OpenAIAdapter:
    """Normalized Responses API adapter with no ambient credentials or vendor imports."""

    def __init__(
        self,
        *,
        model: str,
        credential: str,
        resolver: SecretResolver,
        transport: OpenAITransport,
    ) -> None:
        if not _MODEL.fullmatch(model):
            raise AdapterError("OpenAI model identifier is invalid")
        self._credential = SecretReference.parse(credential)
        self._model = model
        self._resolver = resolver
        self._transport = transport
        self._executions: dict[str, _Execution] = {}

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            "openai",
            "nexus.openai.responses",
            "1.0",
            ProviderCapabilities(frozenset({"stream", "cancel", "resume", "coding"}), True),
            ConformanceLevel.UNVERIFIED,
            HealthState.UNKNOWN,
            str(self._credential),
        )

    async def healthcheck(self) -> HealthState:
        try:
            with secret_scope(self._resolver, self._credential) as secret:
                healthy = await self._transport.health(secret.reveal())
        except Exception as exc:
            raise AdapterError("OpenAI healthcheck failed") from exc
        return HealthState.HEALTHY if healthy else HealthState.UNAVAILABLE

    async def capabilities(self) -> ProviderCapabilities:
        return self.descriptor().capabilities

    async def run(self, task: ProviderTask) -> str:
        if task.provider_task_id in self._executions:
            raise AdapterError("provider task already exists")
        request: Mapping[str, object] = {
            "model": self._model,
            "input": dict(task.input),
            "background": True,
            "store": False,
            "metadata": {"nexus_task_id": task.provider_task_id},
        }
        try:
            with secret_scope(self._resolver, self._credential) as secret:
                response = await self._transport.create(request, secret.reveal())
            execution = self._execution(task, response)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError("OpenAI request failed") from exc
        self._executions[task.provider_task_id] = execution
        return task.provider_task_id

    async def stream_events(self, provider_task_id: str) -> AsyncIterator[ProviderEvent]:
        execution = self._get(provider_task_id)
        for event in tuple(execution.events):
            yield event

    async def result(self, provider_task_id: str) -> ProviderResult:
        execution = self._get(provider_task_id)
        if execution.result is None:
            raise AdapterError("provider task is not terminal")
        return execution.result

    async def cancel(self, provider_task_id: str) -> None:
        execution = self._get(provider_task_id)
        if execution.result is not None:
            return
        try:
            with secret_scope(self._resolver, self._credential) as secret:
                response = await self._transport.cancel_response(
                    execution.response_id, secret.reveal()
                )
            self._apply(execution, response)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError("OpenAI cancellation failed") from exc

    async def resume(self, provider_task_id: str) -> str:
        execution = self._get(provider_task_id)
        if execution.result is not None:
            return provider_task_id
        try:
            with secret_scope(self._resolver, self._credential) as secret:
                response = await self._transport.retrieve(execution.response_id, secret.reveal())
            self._apply(execution, response)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError("OpenAI resume failed") from exc
        return provider_task_id

    def _execution(self, task: ProviderTask, response: Mapping[str, Any]) -> _Execution:
        response_id = response.get("id")
        if not isinstance(response_id, str) or not _RESPONSE_ID.fullmatch(response_id):
            raise AdapterError("invalid provider response identity")
        execution = _Execution(task, response_id, [], None)
        self._append(execution, ProviderEventKind.ACCEPTED, {"response_id": response_id})
        self._append(execution, ProviderEventKind.STARTED, {})
        self._apply(execution, response)
        return execution

    def _apply(self, execution: _Execution, response: Mapping[str, Any]) -> None:
        status = response.get("status")
        if status in {"queued", "in_progress"}:
            return
        mapping = {
            "completed": (TaskStatus.SUCCEEDED, ProviderEventKind.COMPLETED),
            "failed": (TaskStatus.FAILED, ProviderEventKind.FAILED),
            "cancelled": (TaskStatus.CANCELLED, ProviderEventKind.CANCELLED),
            "incomplete": (TaskStatus.FAILED, ProviderEventKind.FAILED),
        }
        if not isinstance(status, str):
            raise AdapterError("invalid provider response status")
        try:
            normalized, event_kind = mapping[status]
        except KeyError as exc:
            raise AdapterError("invalid provider response status") from exc
        usage_value = response.get("usage", {})
        if not isinstance(usage_value, Mapping):
            raise AdapterError("invalid provider response usage")
        try:
            usage = Usage(
                int(usage_value.get("input_tokens", 0)),
                int(usage_value.get("output_tokens", 0)),
                0.0,
            )
        except (TypeError, ValueError) as exc:
            raise AdapterError("invalid provider response usage") from exc
        failure = None
        if normalized is TaskStatus.FAILED:
            failure = Failure(
                FailureClass.PROVIDER,
                "openai_response_failed",
                "OpenAI response did not complete successfully",
                status == "incomplete",
            )
        execution.result = ProviderResult(
            execution.task.provider_task_id,
            normalized,
            usage=usage,
            metadata={"response_id": execution.response_id, "model": self._model},
            failure=failure,
        )
        self._append(execution, event_kind, {"status": normalized.value})

    @staticmethod
    def _append(execution: _Execution, kind: ProviderEventKind, payload: Mapping[str, Any]) -> None:
        sequence = len(execution.events) + 1
        execution.events.append(
            ProviderEvent.create(
                execution.task.provider_task_id,
                sequence,
                _EPOCH + timedelta(microseconds=sequence),
                kind,
                payload,
                execution.task.trace_id,
            )
        )

    def _get(self, provider_task_id: str) -> _Execution:
        try:
            return self._executions[provider_task_id]
        except KeyError as exc:
            raise AdapterError("unknown provider task") from exc
