import json

import pytest

from nexus_os.agent_runtime_api import AgentRuntimeApiError, _artifact_file


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
