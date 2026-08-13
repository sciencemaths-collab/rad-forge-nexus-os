from datetime import timedelta

from nexus_os.agent_api import AgentApiRequest, AgentIdentity
from nexus_os.agent_handoff import AgentRuntimeHandoffService
from nexus_os.agent_runtime_api import AgentRuntimeRegistry, GovernedAgentRuntimeApi
from nexus_os.agent_store import AgentSessionStore
from nexus_os.approval import ApprovalStore
from nexus_os.attempt_store import AttemptStore
from nexus_os.domain import ActionEffect
from nexus_os.evidence import EvidenceLedger
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.retry import RetryEngine, RetryLimits
from nexus_os.runtime import RuntimeOrchestrator
from nexus_os.runtime_evidence import AgentCompletionVerifier, RuntimeEvidenceWriter
from nexus_os.scheduler import GovernedScheduler
from nexus_os.stores import SQLiteCheckpointStore
from nexus_os.tools import ToolDescriptor, ToolExecutor, ToolRegistry
from tests.contract.test_agent_handoff_contract import NOW, SESSION, TRACE, _approved
from tests.unit.test_agent_store import uid


class Capabilities:
    def qualified_capabilities(self, identity, session_id):
        return frozenset({"app_build.planning"})


class Ids:
    number = 500

    def session_id(self):
        return SESSION

    def event_id(self):
        self.number += 1
        return uid(self.number)


def test_facade_starts_and_recovers_runtime_from_durable_graph(tmp_path) -> None:
    sessions = AgentSessionStore(tmp_path / "agent.db")
    _approved(sessions)
    checkpoints = SQLiteCheckpointStore(tmp_path / "runtime.db")
    runtime = RuntimeOrchestrator(checkpoints)
    approvals = ApprovalStore(tmp_path / "approvals.db")
    tools = ToolRegistry()
    tools.register(
        ToolDescriptor(
            "nexus.placeholder",
            "Inert facade fixture tool.",
            ActionEffect.READ_ONLY,
            1,
            True,
            False,
            {"type": "object"},
            {"type": "object"},
        )
    )
    policy = PolicyEngine(PolicyRules())
    evidence = EvidenceLedger(tmp_path / "evidence.db")
    writer = RuntimeEvidenceWriter(evidence)
    scheduler = GovernedScheduler(
        runtime=runtime,
        registry=tools,
        executor=ToolExecutor(tools, policy, approvals),
        policy=policy,
        approvals=approvals,
        attempts=AttemptStore(tmp_path / "attempts.db"),
        retry=RetryEngine(RetryLimits()),
        evidence=writer,
        tool_bindings={"placeholder": "nexus.placeholder"},
    )
    facade = GovernedAgentRuntimeApi(
        sessions=sessions,
        handoff=AgentRuntimeHandoffService(sessions, checkpoints),
        registry=AgentRuntimeRegistry(tmp_path / "registry.db"),
        runtime=runtime,
        scheduler=scheduler,
        approvals=approvals,
        completion=AgentCompletionVerifier(
            sessions=sessions, ledger=evidence, writer=writer, verifiers={}
        ),
        capabilities=Capabilities(),
        ids=Ids(),
    )
    identity = AgentIdentity("owner-user", frozenset({"agent:execute", "agent:read"}), True)
    request = AgentApiRequest(
        "POST", "/v1/agent/runtime", {}, None, "request-1", NOW + timedelta(minutes=5), TRACE
    )
    started = facade.start(SESSION, identity, request, {"workspace_root": "/workspace/project"})
    recovered = facade.status(SESSION)
    assert started["run_state"] == "READY"
    assert recovered == started
    assert sessions.get(SESSION).state.value == "RUNNING"
