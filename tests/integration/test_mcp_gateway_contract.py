import asyncio
import json
from pathlib import Path
from typing import Any

from nexus_os.domain import TraceId
from nexus_os.mcp_gateway import GatewayContext, McpGateway, MemoryAuditSink
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.tools import ToolExecutor, ToolRegistry


def test_frozen_contract_tool_executes_through_json_rpc_gateway() -> None:
    path = Path(__file__).resolve().parents[2] / "contracts" / "mcp" / "tools.json"
    registry = ToolRegistry.from_contract(json.loads(path.read_text(encoding="utf-8")))

    async def verify(arguments: dict[str, Any]) -> dict[str, Any]:
        return {"valid": True, "record_count": 0, "errors": []}

    registry.bind("nexus.evidence.verify", verify)
    gateway = McpGateway(
        registry,
        ToolExecutor(registry, PolicyEngine(PolicyRules())),
        MemoryAuditSink(),
    )
    response = asyncio.run(
        gateway.handle(
            {
                "jsonrpc": "2.0",
                "id": "integration-1",
                "method": "tools/call",
                "params": {
                    "name": "nexus.evidence.verify",
                    "arguments": {"run_id": "00000000-0000-4000-8000-000000000001"},
                },
            },
            GatewayContext(
                "integration",
                "project-1",
                TraceId("3" * 32),
                frozenset({"tools:call"}),
            ),
        )
    )
    assert response["result"]["content"] == {
        "valid": True,
        "record_count": 0,
        "errors": [],
    }
