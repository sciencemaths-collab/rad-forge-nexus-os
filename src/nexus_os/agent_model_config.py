"""Validated Agent reasoning-model profiles and qualification-gated selection."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast
from urllib.parse import urlsplit

import yaml

from nexus_os.local_openai_adapter import LocalOpenAITransport
from nexus_os.model_qualification import ModelUse
from nexus_os.model_registry import ModelQualificationRegistry, ModelRegistryError
from nexus_os.secrets import SecretReference, SecretResolver, secret_scope

MAX_MODEL_CONFIG_BYTES = 64 * 1024
_NAME = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
_ALLOWED_ROOT = frozenset({"schema_version", "selected", "profiles"})
_ALLOWED_PROFILE = frozenset(
    {"type", "base_url", "model", "credential", "adapter_version", "timeout_seconds"}
)


class AgentModelConfigError(ValueError):
    """Safe model configuration, discovery, or selection failure."""


class _NoAliasLoader(yaml.SafeLoader):
    def compose_node(self, parent: yaml.Node | None, index: int) -> yaml.Node:
        if self.check_event(yaml.AliasEvent):  # type: ignore[no-untyped-call]
            raise AgentModelConfigError("YAML aliases are not allowed in model configuration")
        event = self.peek_event()  # type: ignore[no-untyped-call]
        if getattr(event, "anchor", None) is not None:
            raise AgentModelConfigError("YAML anchors are not allowed in model configuration")
        return cast(yaml.Node, super().compose_node(parent, index))


@dataclass(frozen=True, slots=True)
class LocalModelProfile:
    name: str
    provider_type: str
    base_url: str
    model: str | None
    credential: str | None
    adapter_version: str
    timeout_seconds: int

    def public_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "name": self.name,
            "type": self.provider_type,
            "base_url": self.base_url,
            "model": self.model,
            "adapter_version": self.adapter_version,
            "timeout_seconds": self.timeout_seconds,
        }
        if self.credential is not None:
            value["credential"] = "<redacted-reference>"
        return value


@dataclass(frozen=True, slots=True)
class AgentModelConfiguration:
    selected: str
    profiles: Mapping[str, LocalModelProfile]


@dataclass(frozen=True, slots=True)
class ResolvedAgentModel:
    profile: LocalModelProfile
    model: str


def load_agent_model_config(path: Path) -> AgentModelConfiguration:
    try:
        if not path.is_file() or path.stat().st_size > MAX_MODEL_CONFIG_BYTES:
            raise AgentModelConfigError("model configuration file is invalid or oversized")
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            value = json.loads(raw)
        elif path.suffix.lower() in {".yaml", ".yml"}:
            loader = _NoAliasLoader(raw)
            try:
                value = loader.get_single_data()
            finally:
                loader.dispose()  # type: ignore[no-untyped-call]
        else:
            raise AgentModelConfigError("model configuration must use JSON or YAML")
    except AgentModelConfigError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise AgentModelConfigError("model configuration could not be loaded") from exc
    if not isinstance(value, dict) or set(value) - _ALLOWED_ROOT:
        raise AgentModelConfigError("model configuration root is invalid")
    if value.get("schema_version") != "1.0":
        raise AgentModelConfigError("model configuration schema version is unsupported")
    selected = value.get("selected")
    profiles = value.get("profiles")
    if not isinstance(selected, str) or not _NAME.fullmatch(selected):
        raise AgentModelConfigError("selected model profile is invalid")
    if not isinstance(profiles, dict) or not 1 <= len(profiles) <= 32:
        raise AgentModelConfigError("model profiles are invalid")
    parsed: dict[str, LocalModelProfile] = {}
    for name, profile in profiles.items():
        parsed[name] = _profile(name, profile)
    if selected not in parsed:
        raise AgentModelConfigError("selected model profile does not exist")
    return AgentModelConfiguration(selected, MappingProxyType(parsed))


async def resolve_agent_model(
    configuration: AgentModelConfiguration,
    *,
    transport: LocalOpenAITransport,
    qualifications: ModelQualificationRegistry,
    resolver: SecretResolver,
    at: datetime,
    require_qualification: bool = True,
) -> ResolvedAgentModel:
    profile = configuration.profiles[configuration.selected]
    model = profile.model
    key: str | None = None
    scope = None
    if profile.credential is not None:
        scope = secret_scope(resolver, SecretReference.parse(profile.credential))
        key = scope.__enter__().reveal()
    try:
        models: tuple[str, ...] = ()
        if model is None:
            models = await transport.list_models(profile.base_url, key, profile.timeout_seconds)
        healthy = await transport.health(profile.base_url, key, profile.timeout_seconds)
    finally:
        if scope is not None:
            scope.__exit__(None, None, None)
    if model is None:
        if len(models) != 1:
            raise AgentModelConfigError(
                "model must be selected explicitly unless discovery returns exactly one model"
            )
        model = models[0]
    if require_qualification:
        try:
            for use in (ModelUse.CANDIDATE_SPECIFICATION, ModelUse.REPAIR_PROPOSAL):
                qualifications.authorize(
                    provider_id=profile.provider_type,
                    model_id=model,
                    adapter_version=profile.adapter_version,
                    use=use,
                    at=at,
                )
        except ModelRegistryError as exc:
            raise AgentModelConfigError(
                "selected model lacks current qualification for Agent reasoning"
            ) from exc
    if not healthy:
        raise AgentModelConfigError("selected model provider is unavailable")
    return ResolvedAgentModel(profile, model)


def resolve_agent_model_sync(
    configuration: AgentModelConfiguration,
    *,
    transport: LocalOpenAITransport,
    qualifications: ModelQualificationRegistry,
    resolver: SecretResolver,
    at: datetime,
    require_qualification: bool = True,
) -> ResolvedAgentModel:
    return asyncio.run(
        resolve_agent_model(
            configuration,
            transport=transport,
            qualifications=qualifications,
            resolver=resolver,
            at=at,
            require_qualification=require_qualification,
        )
    )


def _profile(name: object, value: Any) -> LocalModelProfile:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise AgentModelConfigError("model profile name is invalid")
    if not isinstance(value, dict) or set(value) - _ALLOWED_PROFILE:
        raise AgentModelConfigError("model profile is invalid")
    provider_type = value.get("type")
    if provider_type not in {"local_openai", "ollama", "lm_studio"}:
        raise AgentModelConfigError("model profile type is unsupported")
    base_url = value.get("base_url")
    model = value.get("model")
    credential = value.get("credential")
    adapter_version = value.get("adapter_version", "1.0")
    timeout = value.get("timeout_seconds", 5)
    if not isinstance(base_url, str) or not 1 <= len(base_url) <= 512:
        raise AgentModelConfigError("model profile base_url is invalid")
    try:
        endpoint = urlsplit(base_url)
        port = endpoint.port
    except ValueError as exc:
        raise AgentModelConfigError("model profile base_url is invalid") from exc
    if (
        endpoint.scheme not in {"http", "https"}
        or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
        or port is None
        or endpoint.path.rstrip("/") != "/v1"
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.query
        or endpoint.fragment
    ):
        raise AgentModelConfigError("model profile must use an explicit loopback /v1 endpoint")
    if model is not None and (
        not isinstance(model, str) or not _MODEL.fullmatch(model) or ".." in model
    ):
        raise AgentModelConfigError("model profile model is invalid")
    if credential is not None:
        SecretReference.parse(credential)
    if adapter_version != "1.0":
        raise AgentModelConfigError("model profile adapter version is unsupported")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 60:
        raise AgentModelConfigError("model profile timeout is invalid")
    return LocalModelProfile(
        name, provider_type, base_url, model, credential, adapter_version, timeout
    )
