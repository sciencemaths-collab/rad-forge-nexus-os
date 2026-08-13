import asyncio
from datetime import timedelta

import pytest

from nexus_os.agent_api import AgentApiRequest, AgentIdentity
from nexus_os.agent_store import AgentSessionStore
from nexus_os.domain import ActionEffect
from nexus_os.local_agent_application import RandomIds, _create_reference_runtime
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.tools import ToolDescriptor, ToolError, ToolExecutor, ToolRegistry
from nexus_os.workspace_tools import register_workspace_artifact_tool
from tests.contract.test_agent_handoff_contract import NOW, SESSION, TRACE, _approved


def test_preview_validates_policy_without_resolving_or_invoking_handler() -> None:
    registry = ToolRegistry()
    invoked = False

    async def handler(payload):  # type: ignore[no-untyped-def]
        nonlocal invoked
        invoked = True
        return {"ok": True}

    registry.register(
        ToolDescriptor(
            "reference.preview",
            "Preview fixture.",
            ActionEffect.SENSITIVE,
            1,
            False,
            True,
            {"type": "object", "required": ["value"]},
            {"type": "object"},
        )
    )
    registry.bind("reference.preview", handler)
    executor = ToolExecutor(registry, PolicyEngine(PolicyRules()))
    preview = executor.preview(
        "reference.preview",
        {"value": 1},
        actor_id="operator",
        project_id="project",
    )
    assert preview.approval_required
    assert preview.decision.value == "REQUIRE_APPROVAL"
    assert preview.input_digest.startswith("sha256:")
    assert not invoked


def test_workspace_tool_is_contained_idempotent_and_conflict_safe(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registry = ToolRegistry()
    register_workspace_artifact_tool(registry)
    executor = ToolExecutor(
        registry,
        PolicyEngine(PolicyRules(allowed_operations=frozenset({"workspace.write_artifact"}))),
    )
    payload = {
        "workspace_root": str(workspace),
        "expected_artifact": "reports/result.json",
        "mode_version": "1.0",
    }
    first = asyncio.run(
        executor.execute(
            "workspace.write_artifact",
            payload,
            actor_id="operator",
            project_id="project",
        )
    )
    second = asyncio.run(
        executor.execute(
            "workspace.write_artifact",
            payload,
            actor_id="operator",
            project_id="project",
        )
    )
    assert first.output["created"] is True
    assert second.replayed is True
    assert (workspace / str(first.output["path"])).is_file()

    with pytest.raises(ToolError, match="validation"):
        executor.preview(
            "workspace.write_artifact",
            {"workspace_root": str(workspace), "expected_artifact": "../escape"},
            actor_id="operator",
            project_id="project",
        )


def test_reference_runtime_executes_one_approved_workspace_task_with_evidence(
    tmp_path,
) -> None:
    sessions = AgentSessionStore(tmp_path / "agent.sqlite")
    _approved(sessions)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ids = RandomIds()
    facade = _create_reference_runtime(tmp_path, sessions, ids)
    identity = AgentIdentity(
        "local-owner",
        frozenset({"agent:execute", "agent:read", "agent:approve"}),
        True,
    )
    request = AgentApiRequest(
        "POST",
        f"/v1/agent/sessions/{SESSION}/runtime",
        {},
        None,
        "phase3-start-0001",
        NOW + timedelta(minutes=1),
        TRACE,
    )
    started = facade.start(
        SESSION,
        identity,
        request,
        {"workspace_root": str(workspace)},
    )
    assert started["run_state"] == "READY"
    ticked = asyncio.run(
        facade.tick(
            SESSION,
            identity,
            AgentApiRequest(
                "POST",
                f"/v1/agent/sessions/{SESSION}/runtime/ticks",
                {},
                None,
                "phase3-tick-00001",
                NOW + timedelta(minutes=2),
                TRACE,
            ),
            None,
        )
    )
    assert ticked["outcome"] == "SUCCEEDED"
    assert (workspace / ".rad-agent-artifacts/specification.md").is_file()
