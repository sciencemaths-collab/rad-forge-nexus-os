import asyncio
from typing import Any

import pytest

from nexus_os.domain import ActionEffect
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.tools import ToolDescriptor, ToolError, ToolExecutor, ToolRegistry


def tool(effect: ActionEffect, *, timeout: float = 0.05) -> ToolDescriptor:
    return ToolDescriptor(
        "nexus.effect",
        "Effect fixture.",
        effect,
        timeout,
        False,
        False,
        {"type": "object", "additionalProperties": False},
        {"type": "object", "additionalProperties": False},
    )


def test_policy_denial_and_approval_requirement_never_call_handler() -> None:
    for effect, rules, expected in (
        (ActionEffect.SENSITIVE, PolicyRules(), "approval"),
        (
            ActionEffect.READ_ONLY,
            PolicyRules(denied_operations=frozenset({"nexus.effect"})),
            "denied",
        ),
    ):
        called = False
        registry = ToolRegistry()
        registry.register(tool(effect))

        async def handler(value: dict[str, Any]) -> dict[str, Any]:
            nonlocal called
            called = True
            return {}

        registry.bind("nexus.effect", handler)
        executor = ToolExecutor(registry, PolicyEngine(rules))
        with pytest.raises(ToolError, match=expected):
            asyncio.run(executor.execute("nexus.effect", {}, actor_id="a", project_id="p"))
        assert called is False


def test_timeout_and_handler_error_are_bounded_and_safe() -> None:
    registry = ToolRegistry()
    registry.register(tool(ActionEffect.READ_ONLY, timeout=0.01))

    async def hanging(value: dict[str, Any]) -> dict[str, Any]:
        await asyncio.Event().wait()
        return {}

    registry.bind("nexus.effect", hanging)
    with pytest.raises(ToolError, match="timed out"):
        asyncio.run(
            ToolExecutor(registry, PolicyEngine(PolicyRules())).execute(
                "nexus.effect", {}, actor_id="a", project_id="p"
            )
        )


def test_invalid_schema_and_oversized_payload_fail_before_handler() -> None:
    with pytest.raises(ToolError, match="schema"):
        ToolDescriptor(
            "nexus.bad",
            "bad",
            ActionEffect.READ_ONLY,
            1,
            False,
            False,
            {"type": "not-a-json-schema-type"},
            {"type": "object"},
        )

    registry = ToolRegistry()
    registry.register(tool(ActionEffect.READ_ONLY))

    async def handler(value: dict[str, Any]) -> dict[str, Any]:
        return {}

    registry.bind("nexus.effect", handler)
    with pytest.raises(ToolError, match="payload"):
        asyncio.run(
            ToolExecutor(registry, PolicyEngine(PolicyRules())).execute(
                "nexus.effect", {"x": "a" * (1024 * 1024 + 1)}, actor_id="a", project_id="p"
            )
        )
