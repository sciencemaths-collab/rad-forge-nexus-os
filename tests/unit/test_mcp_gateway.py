import asyncio
from typing import Any

from nexus_os.domain import ActionEffect, TraceId
from nexus_os.mcp_gateway import GatewayContext, McpGateway, MemoryAuditSink
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.tools import ToolDescriptor, ToolExecutor, ToolRegistry


def gateway() -> tuple[McpGateway, MemoryAuditSink]:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            "nexus.echo",
            "Echo a value.",
            ActionEffect.READ_ONLY,
            1,
            False,
            False,
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["value"],
                "properties": {"value": {"type": "string"}},
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["value"],
                "properties": {"value": {"type": "string"}},
            },
        )
    )

    async def handler(payload: dict[str, Any]) -> dict[str, Any]:
        return {"value": payload["value"]}

    registry.bind("nexus.echo", handler)
    audit = MemoryAuditSink()
    return McpGateway(registry, ToolExecutor(registry, PolicyEngine(PolicyRules())), audit), audit


def context() -> GatewayContext:
    return GatewayContext(
        "actor-1",
        "project-1",
        TraceId("1" * 32),
        frozenset({"tools:read", "tools:call"}),
    )


def test_tools_list_is_deterministic_and_schema_complete() -> None:
    subject, audit = gateway()
    response = asyncio.run(
        subject.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, context())
    )

    assert response["id"] == 1
    item = response["result"]["tools"][0]
    assert item["name"] == "nexus.echo"
    assert item["inputSchema"]["type"] == "object"
    assert item["effect"] == "READ_ONLY"
    assert audit.records[-1].outcome == "allowed"


def test_tools_call_returns_normalized_content_and_trace() -> None:
    subject, audit = gateway()
    response = asyncio.run(
        subject.handle(
            {
                "jsonrpc": "2.0",
                "id": "request-1",
                "method": "tools/call",
                "params": {"name": "nexus.echo", "arguments": {"value": "hello"}},
            },
            context(),
        )
    )

    assert response["result"]["content"] == {"value": "hello"}
    assert response["result"]["trace_id"] == "1" * 32
    assert response["result"]["isError"] is False
    assert audit.records[-1].tool_name == "nexus.echo"


def test_unknown_method_and_invalid_params_return_stable_errors() -> None:
    subject, _ = gateway()
    cases = (
        ({"jsonrpc": "2.0", "id": 1, "method": "unknown", "params": {}}, -32601),
        ({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {}}, -32602),
        ({"jsonrpc": "1.0", "id": 3, "method": "tools/list", "params": {}}, -32600),
    )
    for request, code in cases:
        response = asyncio.run(subject.handle(request, context()))
        assert response["error"]["code"] == code
