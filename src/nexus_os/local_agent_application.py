"""Production composition root for the local NEXUS Agent planning application."""

from __future__ import annotations

import asyncio
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
from nexus_os.agent_handoff import AgentRuntimeHandoffService
from nexus_os.agent_runtime_api import AgentRuntimeRegistry, GovernedAgentRuntimeApi
from nexus_os.agent_model_config import (
    load_agent_model_config,
    resolve_agent_model_sync,
)
from nexus_os.agent_store import AgentSessionStore
from nexus_os.approval import ApprovalStore
from nexus_os.attempt_store import AttemptStore
from nexus_os.anthropic_adapter import AnthropicAdapter
from nexus_os.cloud_http_transport import AnthropicHTTPTransport, OpenAIHTTPTransport
from nexus_os.evidence import EvidenceLedger
from nexus_os.local_openai_adapter import LocalOpenAIAdapter
from nexus_os.loopback_http_transport import LoopbackHTTPTransport
from nexus_os.model_qualification import ModelUse
from nexus_os.model_registry import (
    ModelQualificationRegistry,
    ModelRegistryError,
    RegistryRecord,
)
from nexus_os.openai_adapter import OpenAIAdapter
from nexus_os.operator_auth import OperatorAuthenticator
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.providers import AgentAdapter
from nexus_os.retry import RetryEngine, RetryLimits
from nexus_os.runtime import RuntimeOrchestrator
from nexus_os.runtime_evidence import AgentCompletionVerifier, RuntimeEvidenceWriter
from nexus_os.scheduler import GovernedScheduler
from nexus_os.sandbox import WorkspaceSandbox
from nexus_os.secrets import SecretReference, SecretResolver, secret_scope
from nexus_os.stores import SQLiteCheckpointStore
from nexus_os.tools import ToolExecutor, ToolRegistry
from nexus_os.workspace_tools import register_workspace_artifact_tool

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
    resolver = SecretResolver(environment=os.environ)
    adapter: AgentAdapter
    if selected_profile.provider_type in {"openai", "anthropic"}:
        resolved = _resolve_cloud_model(
            selected_profile,
            qualifications=qualifications,
            resolver=resolver,
            require_qualification=mode == "qualified",
        )
        if selected_profile.provider_type == "openai":
            adapter = OpenAIAdapter(
                model=resolved,
                credential=_required_credential(selected_profile.credential),
                resolver=resolver,
                transport=OpenAIHTTPTransport(timeout_seconds=selected_profile.timeout_seconds),
            )
        else:
            adapter = AnthropicAdapter(
                model=resolved,
                max_tokens=selected_profile.max_tokens,
                credential=_required_credential(selected_profile.credential),
                resolver=resolver,
                transport=AnthropicHTTPTransport(timeout_seconds=selected_profile.timeout_seconds),
            )
        model_id = resolved
    else:
        host = _network_host(selected_profile.base_url)
        sandbox = WorkspaceSandbox(state_dir, network_hosts=(host,))
        transport = LoopbackHTTPTransport(sandbox=sandbox)
        local = resolve_agent_model_sync(
            configuration,
            transport=transport,
            qualifications=qualifications,
            resolver=resolver,
            at=datetime.now(UTC),
            require_qualification=mode == "qualified",
        )
        adapter = LocalOpenAIAdapter(
            base_url=local.profile.base_url,
            model=local.model,
            credential=local.profile.credential,
            resolver=resolver,
            transport=transport,
            health_timeout_seconds=local.profile.timeout_seconds,
        )
        model_id = local.model
    sessions = AgentSessionStore(state_dir / "agent-sessions.sqlite")
    ids = RandomIds()
    controller = AgentReasoningController(
        sessions=sessions,
        qualifications=authorization,
        adapter=adapter,
        provider_id=selected_profile.provider_type,
        model_id=model_id,
        adapter_version=selected_profile.adapter_version,
        ids=ids,
    )
    runtime_api = (
        _create_reference_runtime(state_dir, sessions, ids) if mode == "qualified" else None
    )
    service = AgentApplicationService(
        sessions=sessions,
        controller=controller,
        qualifications=authorization,
        ids=ids,
        runtime=runtime_api,
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


def _required_credential(value: str | None) -> str:
    if value is None:
        raise LocalAgentApplicationError("cloud model credential reference is required")
    return value


def _resolve_cloud_model(
    profile: object,
    *,
    qualifications: ModelQualificationRegistry,
    resolver: SecretResolver,
    require_qualification: bool,
) -> str:
    from nexus_os.agent_model_config import LocalModelProfile

    if not isinstance(profile, LocalModelProfile):
        raise LocalAgentApplicationError("cloud model profile is invalid")
    credential = _required_credential(profile.credential)
    reference = SecretReference.parse(credential)
    transport = (
        OpenAIHTTPTransport(timeout_seconds=profile.timeout_seconds)
        if profile.provider_type == "openai"
        else AnthropicHTTPTransport(timeout_seconds=profile.timeout_seconds)
    )

    async def discover(key: str) -> tuple[bool, tuple[str, ...]]:
        healthy = await transport.health(key)
        models = await transport.list_models(key)
        return healthy, models

    try:
        with secret_scope(resolver, reference) as secret:
            healthy, models = asyncio.run(discover(secret.reveal()))
    except Exception as exc:
        raise LocalAgentApplicationError("cloud model connection failed safely") from exc
    model = profile.model
    if model is None:
        if len(models) != 1:
            raise LocalAgentApplicationError(
                "cloud model must be selected explicitly unless discovery returns one model"
            )
        model = models[0]
    if model not in models:
        raise LocalAgentApplicationError("selected cloud model is not available")
    if not healthy:
        raise LocalAgentApplicationError("selected cloud model provider is unavailable")
    if require_qualification:
        try:
            for use in (ModelUse.CANDIDATE_SPECIFICATION, ModelUse.REPAIR_PROPOSAL):
                qualifications.authorize(
                    provider_id=profile.provider_type,
                    model_id=model,
                    adapter_version=profile.adapter_version,
                    use=use,
                    at=datetime.now(UTC),
                )
        except ModelRegistryError as exc:
            raise LocalAgentApplicationError(
                "selected cloud model lacks current qualification"
            ) from exc
    return model


class ReferenceRuntimeCapabilities:
    _QUALIFIED = frozenset({"app_build.planning", "research.planning", "data_analysis.planning"})

    def qualified_capabilities(self, identity: object, session_id: UUID) -> frozenset[str]:
        del identity, session_id
        return self._QUALIFIED


def _create_reference_runtime(
    state_dir: Path,
    sessions: AgentSessionStore,
    ids: RandomIds,
) -> GovernedAgentRuntimeApi:
    checkpoints = SQLiteCheckpointStore(state_dir / "runtime-checkpoints.sqlite")
    runtime = RuntimeOrchestrator(checkpoints)
    approvals = ApprovalStore(state_dir / "runtime-approvals.sqlite")
    registry = ToolRegistry()
    register_workspace_artifact_tool(registry)
    allowed = frozenset({"workspace.write_artifact"})
    policy = PolicyEngine(PolicyRules(allowed_operations=allowed))
    ledger = EvidenceLedger(state_dir / "runtime-evidence.sqlite")
    writer = RuntimeEvidenceWriter(ledger)
    bindings = {
        kind: "workspace.write_artifact"
        for kind in (
            "mode.app_build.specification",
            "mode.app_build.design",
            "mode.app_build.contract_test",
            "mode.app_build.implementation",
            "mode.app_build.unit_test",
            "mode.app_build.integration_test",
            "mode.app_build.security_test",
            "mode.app_build.failure_test",
            "mode.app_build.evidence",
            "mode.research.protocol",
            "mode.research.source_acquisition",
            "mode.research.source_extraction",
            "mode.research.claim_construction",
            "mode.research.compute",
            "mode.research.synthesis",
            "mode.research.conflict_review",
            "mode.research.citation_verification",
            "mode.research.reproducibility",
            "mode.research.evidence",
            "mode.data_analysis.ingestion",
            "mode.data_analysis.schema",
            "mode.data_analysis.quality",
            "mode.data_analysis.statistics",
            "mode.data_analysis.chart_spec",
            "mode.data_analysis.explanation",
            "mode.data_analysis.persistence",
            "mode.data_analysis.reopen_verify",
            "mode.data_analysis.evidence",
        )
    }
    scheduler = GovernedScheduler(
        runtime=runtime,
        registry=registry,
        executor=ToolExecutor(registry, policy, approvals),
        policy=policy,
        approvals=approvals,
        attempts=AttemptStore(state_dir / "runtime-attempts.sqlite"),
        retry=RetryEngine(RetryLimits()),
        evidence=writer,
        tool_bindings=bindings,
    )
    return GovernedAgentRuntimeApi(
        sessions=sessions,
        handoff=AgentRuntimeHandoffService(sessions, checkpoints),
        registry=AgentRuntimeRegistry(state_dir / "agent-runtime.sqlite"),
        runtime=runtime,
        scheduler=scheduler,
        approvals=approvals,
        completion=AgentCompletionVerifier(
            sessions=sessions,
            ledger=ledger,
            writer=writer,
            verifiers={},
        ),
        capabilities=ReferenceRuntimeCapabilities(),
        ids=ids,
    )
