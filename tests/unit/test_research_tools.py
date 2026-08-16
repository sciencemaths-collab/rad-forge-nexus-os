import asyncio
import json

from nexus_os.domain import ActionEffect
from nexus_os.research_tools import (
    ingest_local_research_sources,
    register_local_research_source_tool,
)
from nexus_os.tools import ToolRegistry


def _workspace(tmp_path):  # type: ignore[no-untyped-def]
    workspace = tmp_path / "workspace"
    sources = workspace / "research-sources"
    sources.mkdir(parents=True)
    (sources / "paper.md").write_text("# Result\nBinding increased in the test system.\n")
    (sources / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "sources": [
                    {
                        "path": "paper.md",
                        "locator": "doi:10.0000/rad.example",
                        "retrieved_at": "2026-08-16T00:00:00Z",
                        "license_access": "Operator-supplied copy for local analysis",
                    }
                ],
            }
        )
    )
    return workspace


def test_research_tool_contract_is_workspace_bounded() -> None:
    registry = ToolRegistry()
    register_local_research_source_tool(registry)
    descriptor = registry.get("research.ingest_local_sources")
    assert descriptor.effect is ActionEffect.WORKSPACE_WRITE
    assert descriptor.approval_required is False
    assert descriptor.idempotent is False
    assert descriptor.input_schema["properties"]["expected_artifact"] == {"const": "sources.json"}


def test_local_sources_produce_deterministic_provenance_artifact(tmp_path) -> None:
    workspace = _workspace(tmp_path)
    payload = {"workspace_root": str(workspace), "expected_artifact": "sources.json"}
    first = asyncio.run(ingest_local_research_sources(payload))
    second = asyncio.run(ingest_local_research_sources(payload))
    document = json.loads((workspace / first["path"]).read_text())

    assert first["created"] is True
    assert second == {**first, "created": False}
    assert first["source_count"] == 1
    assert first["source_set_digest"].startswith("sha256:")
    source = document["sources"][0]
    assert source["locator"] == "doi:10.0000/rad.example"
    assert source["content_digest"].startswith("sha256:")
    assert source["extracted_text_digest"].startswith("sha256:")
    assert source["provenance"]["workspace_path"] == "research-sources/paper.md"
    assert source["text"].startswith("# Result")
