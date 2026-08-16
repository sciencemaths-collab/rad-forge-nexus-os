import json

import pytest

from nexus_os.agent_runtime_api import AgentRuntimeApiError, _artifact_file
from nexus_os.research_tools import ingest_local_research_sources


def artifact_body() -> bytes:
    return (
        json.dumps(
            {
                "schema_version": "1.0",
                "tool": "workspace.write_artifact",
                "task_input": {"accepted": True},
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def test_only_governed_json_artifact_inside_declared_workspace_is_read(tmp_path) -> None:
    root = tmp_path / "workspace"
    target = root / ".rad-agent-artifacts" / "reports" / "result.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(artifact_body())

    artifact = _artifact_file(
        {"workspace_root": str(root), "expected_artifact": "reports/result.json"}
    )

    assert artifact is not None
    relative, body = artifact
    assert str(relative) == ".rad-agent-artifacts/reports/result.json"
    assert body == artifact_body()


def test_artifact_download_rejects_escape_symlink_and_wrong_provenance(tmp_path) -> None:
    root = tmp_path / "workspace"
    artifact_root = root / ".rad-agent-artifacts"
    artifact_root.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_bytes(artifact_body())
    (artifact_root / "linked.json").symlink_to(outside)
    (artifact_root / "wrong.json").write_text('{"tool":"untrusted"}', encoding="utf-8")

    with pytest.raises(AgentRuntimeApiError, match="boundary"):
        _artifact_file({"workspace_root": str(root), "expected_artifact": "../outside.json"})
    with pytest.raises(AgentRuntimeApiError, match="boundary"):
        _artifact_file({"workspace_root": str(root), "expected_artifact": "linked.json"})
    with pytest.raises(AgentRuntimeApiError, match="provenance"):
        _artifact_file({"workspace_root": str(root), "expected_artifact": "wrong.json"})


def test_research_source_download_revalidates_nested_provenance(tmp_path) -> None:
    root = tmp_path / "workspace"
    sources = root / "research-sources"
    sources.mkdir(parents=True)
    (sources / "paper.md").write_text("# Finding\nObserved binding.\n")
    (sources / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "sources": [
                    {
                        "path": "paper.md",
                        "locator": "doi:10.0000/download.example",
                        "retrieved_at": "2026-08-16T00:00:00Z",
                        "license_access": "Local fixture",
                    }
                ],
            }
        )
    )
    __import__("asyncio").run(
        ingest_local_research_sources(
            {"workspace_root": str(root), "expected_artifact": "sources.json"}
        )
    )
    task_input = {"workspace_root": str(root), "expected_artifact": "sources.json"}
    assert _artifact_file(task_input) is not None

    target = root / ".rad-agent-artifacts/sources.json"
    document = json.loads(target.read_text())
    document["sources"][0]["text"] = "tampered"
    target.write_text(json.dumps(document))
    with pytest.raises(AgentRuntimeApiError, match="provenance"):
        _artifact_file(task_input)
