import asyncio
from typing import Any

import pytest

from nexus_os.domain import ActionEffect
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.tools import ToolDescriptor, ToolError, ToolExecutor, ToolRegistry


def descriptor(
    name: str = "nexus.echo", effect: ActionEffect = ActionEffect.READ_ONLY
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description="Return one validated value.",
        effect=effect,
        timeout_seconds=1.0,
        idempotent=True,
        approval_required=False,
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "idempotency_key"],
            "properties": {
                "value": {"type": "string"},
                "idempotency_key": {"type": "string", "minLength": 16},
            },
        },
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["value"],
            "properties": {"value": {"type": "string"}},
        },
    )


def test_registry_is_sorted_and_duplicate_safe() -> None:
    registry = ToolRegistry()
    registry.register(descriptor("nexus.zed"))
    registry.register(descriptor("nexus.alpha"))

    assert [item.name for item in registry.descriptors()] == ["nexus.alpha", "nexus.zed"]
    with pytest.raises(ToolError, match="already registered"):
        registry.register(descriptor("nexus.alpha"))
    with pytest.raises(ToolError, match="not registered"):
        registry.get("nexus.missing")


def test_executor_validates_input_output_and_runs_allowed_handler() -> None:
    registry = ToolRegistry()
    registry.register(descriptor())

    async def handler(value: dict[str, Any]) -> dict[str, Any]:
        return {"value": value["value"]}

    registry.bind("nexus.echo", handler)
    executor = ToolExecutor(registry, PolicyEngine(PolicyRules()))

    result = asyncio.run(
        executor.execute(
            "nexus.echo",
            {"value": "ok", "idempotency_key": "1234567890abcdef"},
            actor_id="runtime",
            project_id="project-1",
        )
    )
    assert result.output == {"value": "ok"}
    assert result.replayed is False

    with pytest.raises(ToolError, match="input validation"):
        asyncio.run(
            executor.execute(
                "nexus.echo", {"value": "bad", "extra": True},
                actor_id="runtime", project_id="project-1"
            )
        )


def test_idempotent_replay_returns_same_result_without_second_effect() -> None:
    calls = 0
    registry = ToolRegistry()
    registry.register(descriptor())

    async def handler(value: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"value": value["value"]}

    registry.bind("nexus.echo", handler)
    executor = ToolExecutor(registry, PolicyEngine(PolicyRules()))
    payload = {"value": "same", "idempotency_key": "1234567890abcdef"}
    first = asyncio.run(executor.execute("nexus.echo", payload, actor_id="a", project_id="p"))
    second = asyncio.run(executor.execute("nexus.echo", payload, actor_id="a", project_id="p"))

    assert calls == 1
    assert first.output == second.output
    assert second.replayed is True

    changed = {"value": "different", "idempotency_key": "1234567890abcdef"}
    with pytest.raises(ToolError, match="different input"):
        asyncio.run(executor.execute("nexus.echo", changed, actor_id="a", project_id="p"))
