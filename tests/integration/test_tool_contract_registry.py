import json
from pathlib import Path

from nexus_os.domain import ActionEffect
from nexus_os.tools import ToolRegistry


def test_frozen_mcp_tool_contract_loads_into_sorted_registry() -> None:
    contract_path = Path(__file__).resolve().parents[2] / "contracts" / "mcp" / "tools.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    registry = ToolRegistry.from_contract(contract)

    assert [item.name for item in registry.descriptors()] == [
        "nexus.evidence.verify",
        "nexus.project.plan",
        "nexus.run.start",
    ]
    assert registry.get("nexus.run.start").effect is ActionEffect.WORKSPACE_WRITE
    assert all(item.idempotent for item in registry.descriptors())
