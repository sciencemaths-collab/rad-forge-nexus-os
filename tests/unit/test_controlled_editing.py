import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from nexus_os.controlled_editing import apply_text_changes, register_controlled_editing_tool
from nexus_os.domain import ActionEffect
from nexus_os.policy import PolicyEngine, PolicyRules
from nexus_os.tools import ToolError, ToolExecutor, ToolRegistry


def _sha(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _payload(root: Path, changes: list[dict[str, object]]) -> dict[str, object]:
    artifact = {
        "schema_version": "1.0",
        "title": "Apply reviewed changes",
        "summary": "Exact replacements.",
        "sections": [{"heading": "Scope", "content": "Only declared files."}],
        "evidence_notes": [],
        "unresolved_questions": [],
        "file_changes": changes,
    }
    encoded = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    return {
        "workspace_root": str(root),
        "reasoned_artifact": artifact,
        "reasoned_artifact_digest": _sha(encoded),
    }


def test_editing_tool_is_sensitive_and_requires_exact_approval() -> None:
    registry = ToolRegistry()
    register_controlled_editing_tool(registry)
    descriptor = registry.get("workspace.apply_text_changes")
    assert descriptor.effect is ActionEffect.SENSITIVE
    assert descriptor.approval_required is True


def test_executor_cannot_mutate_without_approval(tmp_path: Path) -> None:
    registry = ToolRegistry()
    register_controlled_editing_tool(registry)
    executor = ToolExecutor(
        registry,
        PolicyEngine(PolicyRules(allowed_operations=frozenset({"workspace.apply_text_changes"}))),
    )
    payload = _payload(
        tmp_path,
        [{"path": "app.py", "expected_sha256": None, "content": "value = 1\n"}],
    )
    with pytest.raises(ToolError, match="requires approval"):
        asyncio.run(
            executor.execute(
                "workspace.apply_text_changes",
                payload,
                actor_id="owner",
                project_id="project",
            )
        )
    assert not (tmp_path / "app.py").exists()


def test_applies_update_and_create_with_rollback_evidence(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    original = b"value = 1\n"
    source.write_bytes(original)
    payload = _payload(
        tmp_path,
        [
            {"path": "app.py", "expected_sha256": _sha(original), "content": "value = 2\n"},
            {
                "path": "tests/test_app.py",
                "expected_sha256": None,
                "content": "def test_ok():\n    assert True\n",
            },
        ],
    )
    result = asyncio.run(apply_text_changes(payload))
    assert source.read_text(encoding="utf-8") == "value = 2\n"
    assert (tmp_path / "tests/test_app.py").is_file()
    summary = json.loads((tmp_path / result["path"]).read_text(encoding="utf-8"))
    rollback = json.loads((tmp_path / summary["rollback_path"]).read_text(encoding="utf-8"))
    assert rollback["files"][0]["original_content"] == "value = 1\n"
    assert result["files_changed"] == 2


def test_rejects_stale_digest_traversal_secrets_and_symlink(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("value = 1\n", encoding="utf-8")
    outside = tmp_path.parent / "phase8c-outside.py"
    outside.write_text("outside\n", encoding="utf-8")
    (tmp_path / "link.py").symlink_to(outside)
    cases = [
        {"path": "app.py", "expected_sha256": "sha256:" + "0" * 64, "content": "x\n"},
        {"path": "../escape.py", "expected_sha256": None, "content": "x\n"},
        {"path": ".env", "expected_sha256": None, "content": "x\n"},
        {"path": "link.py", "expected_sha256": _sha(outside.read_bytes()), "content": "x\n"},
    ]
    for change in cases:
        with pytest.raises(ToolError):
            asyncio.run(apply_text_changes(_payload(tmp_path, [change])))
    assert source.read_text(encoding="utf-8") == "value = 1\n"
    assert outside.read_text(encoding="utf-8") == "outside\n"
