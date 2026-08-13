"""Local OpenAI-compatible Chat Completions adapter with an injected transport."""

from __future__ import annotations

import math
import re
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import SplitResult, urlsplit

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

_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
_COMPLETION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)
_MAX_MESSAGES = 64
_MAX_CONTENT = 100_000
_MAX_TOTAL_CONTENT = 250_000


class TransportError(RuntimeError):
    """Local transport failure whose raw text never crosses the adapter boundary."""


class LocalOpenAITransport(Protocol):
    async def health(self, base_url: str, api_key: str | None, timeout_seconds: int) -> bool: ...

    async def create_chat_completion(
        self,
        base_url: str,
        request: Mapping[str, object],
        api_key: str | None,
        timeout_seconds: int,
    ) -> Mapping[str, Any]: ...


@dataclass(slots=True)
class _Execution:
    task: ProviderTask
    completion_id: str
    events: list[ProviderEvent]
    result: ProviderResult


class LocalOpenAIAdapter:
    """Normalize a credential-optional loopback Chat Completions provider."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        credential: str | None,
        resolver: SecretResolver,
        transport: LocalOpenAITransport,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        health_timeout_seconds: int = 5,
    ) -> None:
        self._base_url = _validate_base_url(base_url)
        if not _MODEL.fullmatch(model) or ".." in model or "//" in model or model.endswith("/"):
            raise AdapterError("local model identifier is invalid")
        if (
            not isinstance(max_tokens, int)
            or isinstance(max_tokens, bool)
            or not 1 <= max_tokens <= 200_000
        ):
            raise AdapterError("local max_tokens is invalid")
        if (
            not isinstance(temperature, (int, float))
            or isinstance(temperature, bool)
            or not math.isfinite(temperature)
            or not 0 <= temperature <= 2
        ):
            raise AdapterError("local temperature is invalid")
        if (
            not isinstance(health_timeout_seconds, int)
            or isinstance(health_timeout_seconds, bool)
            or not 1 <= health_timeout_seconds <= 60
        ):
            raise AdapterError("local health timeout is invalid")
        self._credential = SecretReference.parse(credential) if credential is not None else None
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = float(temperature)
        self._health_timeout = health_timeout_seconds
        self._resolver = resolver
        self._transport = transport
        self._executions: dict[str, _Execution] = {}

    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            "local_openai",
            "nexus.local_openai.chat_completions",
            "1.0",
            ProviderCapabilities(
                frozenset({"chat_completions", "reasoning", "local", "credential_optional"}),
                False,
            ),
            ConformanceLevel.UNVERIFIED,
            HealthState.UNKNOWN,
            str(self._credential) if self._credential is not None else None,
        )

    async def healthcheck(self) -> HealthState:
        try:
            healthy = await self._with_key_health()
        except Exception as exc:
            raise AdapterError("local provider healthcheck failed") from exc
        return HealthState.HEALTHY if healthy else HealthState.UNAVAILABLE

    async def capabilities(self) -> ProviderCapabilities:
        return self.descriptor().capabilities

    async def run(self, task: ProviderTask) -> str:
        if task.provider_task_id in self._executions:
            raise AdapterError("provider task already exists")
        request: Mapping[str, object] = {
            "model": self._model,
            "messages": _messages(task.input),
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "stream": False,
        }
        try:
            response = await self._with_key_create(request, task.timeout_seconds)
            execution = self._normalize(task, response)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError("local provider request failed") from exc
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
        raise AdapterError("local provider resume is not supported")

    async def _with_key_health(self) -> bool:
        if self._credential is None:
            return await self._transport.health(self._base_url, None, self._health_timeout)
        with secret_scope(self._resolver, self._credential) as secret:
            return await self._transport.health(
                self._base_url, secret.reveal(), self._health_timeout
            )

    async def _with_key_create(
        self, request: Mapping[str, object], timeout_seconds: int
    ) -> Mapping[str, Any]:
        if self._credential is None:
            return await self._transport.create_chat_completion(
                self._base_url, request, None, timeout_seconds
            )
        with secret_scope(self._resolver, self._credential) as secret:
            return await self._transport.create_chat_completion(
                self._base_url, request, secret.reveal(), timeout_seconds
            )

    def _normalize(self, task: ProviderTask, response: Mapping[str, Any]) -> _Execution:
        completion_id = response.get("id")
        if not isinstance(completion_id, str) or not _COMPLETION_ID.fullmatch(completion_id):
            raise AdapterError("invalid local provider response identity")
        if response.get("object") != "chat.completion":
            raise AdapterError("invalid local provider response object")
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise AdapterError("invalid local provider response choices")
        choice = choices[0]
        if not isinstance(choice, Mapping) or choice.get("index") != 0:
            raise AdapterError("invalid local provider response choice")
        message = choice.get("message")
        if (
            not isinstance(message, Mapping)
            or message.get("role") != "assistant"
            or not isinstance(message.get("content"), str)
            or not 1 <= len(message["content"]) <= _MAX_CONTENT
        ):
            raise AdapterError("invalid local provider response message")
        finish_reason = choice.get("finish_reason")
        if finish_reason not in {"stop", "length", "content_filter"}:
            raise AdapterError("invalid local provider response finish reason")
        usage = _usage(response.get("usage"))
        succeeded = finish_reason == "stop"
        status = TaskStatus.SUCCEEDED if succeeded else TaskStatus.FAILED
        failure = None
        if not succeeded:
            failure = Failure(
                FailureClass.PROVIDER,
                "local_completion_incomplete",
                "Local provider did not complete the response",
                finish_reason == "length",
            )
        events: list[ProviderEvent] = []
        execution = _Execution(
            task,
            completion_id,
            events,
            ProviderResult(
                task.provider_task_id,
                status,
                usage=usage,
                metadata={
                    "completion_id": completion_id,
                    "model": self._model,
                    "output_text": message["content"],
                    "finish_reason": finish_reason,
                },
                failure=failure,
            ),
        )
        self._append(execution, ProviderEventKind.ACCEPTED, {"completion_id": completion_id})
        self._append(execution, ProviderEventKind.STARTED, {})
        terminal = ProviderEventKind.COMPLETED if succeeded else ProviderEventKind.FAILED
        self._append(execution, terminal, {"status": status.value})
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


def _validate_base_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 512:
        raise AdapterError("local base URL is invalid")
    try:
        parsed: SplitResult = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise AdapterError("local base URL is invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in _LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != "/v1"
        or port is None
        or not 1 <= port <= 65535
    ):
        raise AdapterError("local base URL must be an explicit loopback /v1 endpoint")
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    return f"{parsed.scheme}://{host}:{port}/v1"


def _messages(value: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_messages = value.get("messages")
    if raw_messages is None:
        prompt = value.get("prompt", value.get("instructions"))
        system = value.get("system")
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= _MAX_CONTENT:
            raise AdapterError("local provider prompt is invalid")
        if system is not None and (
            not isinstance(system, str) or not 1 <= len(system) <= _MAX_CONTENT
        ):
            raise AdapterError("local provider system message is invalid")
        messages = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages
    if not isinstance(raw_messages, (list, tuple)) or not 1 <= len(raw_messages) <= _MAX_MESSAGES:
        raise AdapterError("local provider messages are invalid")
    messages = []
    total = 0
    for item in raw_messages:
        if not isinstance(item, Mapping) or set(item) != {"role", "content"}:
            raise AdapterError("local provider message is invalid")
        role = item.get("role")
        content = item.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            raise AdapterError("local provider message is invalid")
        if not 1 <= len(content) <= _MAX_CONTENT:
            raise AdapterError("local provider message content is invalid")
        total += len(content)
        messages.append({"role": role, "content": content})
    if total > _MAX_TOTAL_CONTENT:
        raise AdapterError("local provider message content is too large")
    return messages


def _usage(value: object) -> Usage:
    if value is None:
        return Usage(0, 0, 0.0)
    if not isinstance(value, Mapping):
        raise AdapterError("invalid local provider response usage")
    prompt = value.get("prompt_tokens", 0)
    completion = value.get("completion_tokens", 0)
    total = value.get(
        "total_tokens",
        prompt + completion if isinstance(prompt, int) and isinstance(completion, int) else None,
    )
    if (
        not isinstance(prompt, int)
        or isinstance(prompt, bool)
        or prompt < 0
        or not isinstance(completion, int)
        or isinstance(completion, bool)
        or completion < 0
        or not isinstance(total, int)
        or isinstance(total, bool)
        or total != prompt + completion
    ):
        raise AdapterError("invalid local provider response usage")
    return Usage(prompt, completion, 0.0)
