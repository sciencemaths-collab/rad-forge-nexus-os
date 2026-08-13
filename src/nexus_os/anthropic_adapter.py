"""Anthropic Messages adapter behind an injected vendor transport."""

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
_MESSAGE_ID = re.compile(r"^msg_[A-Za-z0-9_-]{1,120}$")
_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


class TransportError(RuntimeError):
    """Vendor-transport failure whose raw text stays behind the adapter."""


class AnthropicTransport(Protocol):
    async def health(self, api_key: str) -> bool: ...

    async def create(self, request: Mapping[str, object], api_key: str) -> Mapping[str, Any]: ...


@dataclass(slots=True)
class _Execution:
    task: ProviderTask
    message_id: str
    events: list[ProviderEvent]
    result: ProviderResult


class AnthropicAdapter:
    """Normalized Messages adapter with truthful non-resumable capabilities."""

    def __init__(
        self,
        *,
        model: str,
        max_tokens: int,
        credential: str,
        resolver: SecretResolver,
        transport: AnthropicTransport,
    ) -> None:
        if not _MODEL.fullmatch(model):
            raise AdapterError("Anthropic model identifier is invalid")
        if (
            not isinstance(max_tokens, int)
            or isinstance(max_tokens, bool)
            or not 1 <= max_tokens <= 200_000
        ):
            raise AdapterError("Anthropic max_tokens is invalid")
        self._credential = SecretReference.parse(credential)
        self._model = model
        self._max_tokens = max_tokens
        self._resolver = resolver
        self._transport = transport
        self._executions: dict[str, _Execution] = {}

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            "anthropic",
            "nexus.anthropic.messages",
            "1.0",
            ProviderCapabilities(frozenset({"stream", "cancel", "coding"}), False),
            ConformanceLevel.UNVERIFIED,
            HealthState.UNKNOWN,
            str(self._credential),
        )

    async def healthcheck(self) -> HealthState:
        try:
            with secret_scope(self._resolver, self._credential) as secret:
                healthy = await self._transport.health(secret.reveal())
        except Exception as exc:
            raise AdapterError("Anthropic healthcheck failed") from exc
        return HealthState.HEALTHY if healthy else HealthState.UNAVAILABLE

    async def capabilities(self) -> ProviderCapabilities:
        return self.descriptor().capabilities

    async def run(self, task: ProviderTask) -> str:
        if task.provider_task_id in self._executions:
            raise AdapterError("provider task already exists")
        request: Mapping[str, object] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": _prompt(task.input)}],
            **_system(task.input),
            "metadata": {"user_id": task.provider_task_id},
        }
        try:
            with secret_scope(self._resolver, self._credential) as secret:
                message = await self._transport.create(request, secret.reveal())
            execution = self._normalize(task, message)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError("Anthropic request failed") from exc
        self._executions[task.provider_task_id] = execution
        return task.provider_task_id

    async def stream_events(self, provider_task_id: str) -> AsyncIterator[ProviderEvent]:
        execution = self._get(provider_task_id)
        for event in tuple(execution.events):
            yield event

    async def result(self, provider_task_id: str) -> ProviderResult:
        return self._get(provider_task_id).result

    async def cancel(self, provider_task_id: str) -> None:
        self._get(provider_task_id)

    async def resume(self, provider_task_id: str) -> str:
        self._get(provider_task_id)
        raise AdapterError("resume is not supported")

    def _normalize(self, task: ProviderTask, message: Mapping[str, Any]) -> _Execution:
        message_id = message.get("id")
        if (
            message.get("type") != "message"
            or message.get("role") != "assistant"
            or not isinstance(message_id, str)
            or not _MESSAGE_ID.fullmatch(message_id)
        ):
            raise AdapterError("invalid provider message identity")
        stop_reason = message.get("stop_reason")
        if not isinstance(stop_reason, str):
            raise AdapterError("invalid provider message stop reason")
        successes = {"end_turn", "stop_sequence", "tool_use", "pause_turn"}
        failures = {"max_tokens", "refusal", "model_context_window_exceeded"}
        if stop_reason not in successes | failures:
            raise AdapterError("invalid provider message stop reason")
        usage_value = message.get("usage", {})
        if not isinstance(usage_value, Mapping):
            raise AdapterError("invalid provider message usage")
        try:
            usage = Usage(
                int(usage_value.get("input_tokens", 0)),
                int(usage_value.get("output_tokens", 0)),
                0.0,
            )
        except (TypeError, ValueError) as exc:
            raise AdapterError("invalid provider message usage") from exc

        events: list[ProviderEvent] = []
        execution = _Execution(
            task,
            message_id,
            events,
            ProviderResult(task.provider_task_id, TaskStatus.SUCCEEDED),
        )
        self._append(execution, ProviderEventKind.ACCEPTED, {"message_id": message_id})
        self._append(execution, ProviderEventKind.STARTED, {})
        status = TaskStatus.SUCCEEDED if stop_reason in successes else TaskStatus.FAILED
        failure = None
        if status is TaskStatus.FAILED:
            failure = Failure(
                FailureClass.PROVIDER,
                "anthropic_message_incomplete",
                "Anthropic message did not complete successfully",
                stop_reason in {"max_tokens", "model_context_window_exceeded"},
            )
        output_text = _output_text(message)
        if status is TaskStatus.SUCCEEDED and output_text is None:
            raise AdapterError("invalid provider message output")
        metadata: dict[str, object] = {
            "message_id": message_id,
            "model": self._model,
            "stop_reason": stop_reason,
        }
        if output_text is not None:
            metadata["output_text"] = output_text
        execution.result = ProviderResult(
            task.provider_task_id,
            status,
            usage=usage,
            metadata=metadata,
            failure=failure,
        )
        kind = (
            ProviderEventKind.COMPLETED
            if status is TaskStatus.SUCCEEDED
            else ProviderEventKind.FAILED
        )
        self._append(execution, kind, {"status": status.value})
        return execution

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


def _prompt(value: Mapping[str, Any]) -> str:
    prompt = value.get("prompt", value.get("instructions"))
    if not isinstance(prompt, str) or not 1 <= len(prompt) <= 100_000:
        raise AdapterError("Anthropic prompt is invalid")
    return prompt


def _system(value: Mapping[str, Any]) -> dict[str, str]:
    system = value.get("system")
    if system is None:
        return {}
    if not isinstance(system, str) or not 1 <= len(system) <= 100_000:
        raise AdapterError("Anthropic system message is invalid")
    return {"system": system}


def _output_text(message: Mapping[str, Any]) -> str | None:
    content = message.get("content")
    if not isinstance(content, list):
        return None
    texts = []
    for item in content:
        if isinstance(item, Mapping) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                texts.append(text)
    combined = "".join(texts)
    return combined if 1 <= len(combined) <= 100_000 else None
