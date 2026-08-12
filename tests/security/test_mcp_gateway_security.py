import asyncio

from nexus_os.domain import TraceId
from nexus_os.mcp_gateway import GatewayContext, McpGateway, MemoryAuditSink
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.tools import ToolExecutor, ToolRegistry


def subject(*, max_calls: int = 2) -> McpGateway:
    registry = ToolRegistry()
    return McpGateway(
        registry,
        ToolExecutor(registry, PolicyEngine(PolicyRules())),
        MemoryAuditSink(),
        max_calls_per_actor=max_calls,
    )


def ctx(scopes: frozenset[str] = frozenset({"tools:read"})) -> GatewayContext:
    return GatewayContext("actor", "project", TraceId("2" * 32), scopes)


def test_missing_scope_fails_before_tool_lookup() -> None:
    response = asyncio.run(
        subject().handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "does.not.exist", "arguments": {}},
            },
            ctx(),
        )
    )
    assert response["error"]["code"] == -32001
    assert "does.not.exist" not in str(response)


def test_request_cannot_override_trusted_identity_or_project() -> None:
    response = asyncio.run(
        subject().handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {"actor_id": "admin", "project_id": "other"},
            },
            ctx(),
        )
    )
    assert response["error"]["code"] == -32602


def test_rate_limit_is_deterministic_per_authenticated_actor() -> None:
    gateway = subject(max_calls=1)
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    assert "result" in asyncio.run(gateway.handle(request, ctx()))
    limited = asyncio.run(gateway.handle(request, ctx()))
    assert limited["error"]["code"] == -32002


def test_oversized_and_hostile_request_ids_are_rejected_safely() -> None:
    for request_id in (True, "x" * 257, {"nested": "id"}):
        response = asyncio.run(
            subject().handle(
                {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}},
                ctx(),
            )
        )
        assert response["error"]["code"] == -32600
