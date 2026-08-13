"""Production composition root for the local NEXUS Agent planning application."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from nexus_os.agent_api import (
    AgentApplication,
    AgentApplicationService,
    DurableReplayStore,
)
from nexus_os.agent_controller import AgentReasoningController
from nexus_os.agent_model_config import (
    load_agent_model_config,
    resolve_agent_model_sync,
)
from nexus_os.agent_store import AgentSessionStore
from nexus_os.local_openai_adapter import LocalOpenAIAdapter
from nexus_os.loopback_http_transport import LoopbackHTTPTransport
from nexus_os.model_qualification import ModelUse
from nexus_os.model_registry import (
    ModelQualificationRegistry,
    ModelRegistryError,
    RegistryRecord,
)
from nexus_os.operator_auth import OperatorAuthenticator
from nexus_os.sandbox import WorkspaceSandbox
from nexus_os.secrets import SecretResolver

MODEL_CONFIG_ENV = "RAD_AGENT_MODEL_CONFIG"
MODEL_ATTESTATION_ENV = "RAD_AGENT_MODEL_ATTESTATION"
MODE_ENV = "RAD_AGENT_MODE"
_LEGACY_MODEL_CONFIG_ENV = "NEXUS_AGENT_MODEL_CONFIG"
_LEGACY_MODEL_ATTESTATION_ENV = "NEXUS_AGENT_MODEL_ATTESTATION"


class LocalAgentApplicationError(ValueError):
    """Safe local composition or bootstrap failure."""


class DevelopmentModelAuthorization:
    """Explicitly unqualified authorization limited to proposal-only local development."""

    _ALLOWED = frozenset({ModelUse.CANDIDATE_SPECIFICATION, ModelUse.REPAIR_PROPOSAL})

    def authorize(
        self,
        *,
        provider_id: str,
        model_id: str,
        adapter_version: str,
        use: ModelUse,
        at: datetime,
    ) -> object:
        del provider_id, model_id, adapter_version
        if at.tzinfo is None or use not in self._ALLOWED:
            raise ModelRegistryError("development mode does not authorize this model use")
        return object()

    def active(self, *, at: datetime) -> tuple[RegistryRecord, ...]:
        del at
        return ()


class RandomIds:
    def session_id(self) -> UUID:
        return uuid4()

    def candidate_id(self) -> UUID:
        return uuid4()

    def event_id(self) -> UUID:
        return uuid4()


def create_local_application(
    authenticator: OperatorAuthenticator, state_dir: Path
) -> AgentApplication:
    """Assemble the authenticated, qualified, durable local planning application."""
    mode = os.environ.get(MODE_ENV, "qualified")
    if mode not in {"development", "qualified"}:
        raise LocalAgentApplicationError(f"{MODE_ENV} must be development or qualified")
    config_value = os.environ.get(MODEL_CONFIG_ENV) or os.environ.get(_LEGACY_MODEL_CONFIG_ENV)
    if config_value is None:
        raise LocalAgentApplicationError(f"{MODEL_CONFIG_ENV} must name a model configuration")
    config_path = Path(config_value)
    qualifications = ModelQualificationRegistry(state_dir / "model-qualifications.sqlite")
    if mode == "qualified":
        _bootstrap_qualification(qualifications)
    authorization = DevelopmentModelAuthorization() if mode == "development" else qualifications
    configuration = load_agent_model_config(config_path)
    selected_profile = configuration.profiles[configuration.selected]
    host = _network_host(selected_profile.base_url)
    sandbox = WorkspaceSandbox(state_dir, network_hosts=(host,))
    transport = LoopbackHTTPTransport(sandbox=sandbox)
    resolver = SecretResolver(environment=os.environ)
    resolved = resolve_agent_model_sync(
        configuration,
        transport=transport,
        qualifications=qualifications,
        resolver=resolver,
        at=datetime.now(UTC),
        require_qualification=mode == "qualified",
    )
    adapter = LocalOpenAIAdapter(
        base_url=resolved.profile.base_url,
        model=resolved.model,
        credential=resolved.profile.credential,
        resolver=resolver,
        transport=transport,
        health_timeout_seconds=resolved.profile.timeout_seconds,
    )
    sessions = AgentSessionStore(state_dir / "agent-sessions.sqlite")
    ids = RandomIds()
    controller = AgentReasoningController(
        sessions=sessions,
        qualifications=authorization,
        adapter=adapter,
        provider_id=resolved.profile.provider_type,
        model_id=resolved.model,
        adapter_version=resolved.profile.adapter_version,
        ids=ids,
    )
    service = AgentApplicationService(
        sessions=sessions,
        controller=controller,
        qualifications=authorization,
        ids=ids,
    )
    return AgentApplication(
        authenticator=authenticator,
        service=service,
        replays=DurableReplayStore(state_dir / "agent-api-replays.sqlite"),
    )


def _bootstrap_qualification(registry: ModelQualificationRegistry) -> None:
    path_value = os.environ.get(MODEL_ATTESTATION_ENV) or os.environ.get(
        _LEGACY_MODEL_ATTESTATION_ENV
    )
    if path_value is None:
        if not registry.active(at=datetime.now(UTC)):
            raise LocalAgentApplicationError(
                f"{MODEL_ATTESTATION_ENV} is required until a qualification is registered"
            )
        return
    path = Path(path_value)
    try:
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise LocalAgentApplicationError("model attestation file is invalid")
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError
        if not registry.active(at=datetime.now(UTC)):
            registry.register(
                document,
                registered_at=datetime.now(UTC),
                registered_by="local-application-bootstrap",
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise LocalAgentApplicationError("model attestation could not be registered") from exc


def _network_host(base_url: str) -> str:
    if "[::1]" in base_url:
        return "::1"
    return "127.0.0.1"
