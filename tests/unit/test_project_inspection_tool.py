import asyncio
import json
from pathlib import Path

import pytest

from nexus_os.domain import ActionEffect, TaskDefinition, TaskId
from nexus_os.project_inspection import (
    ProjectInventoryContext,
    inspect_project,
    register_project_inspection_tool,
)
from nexus_os.tools import ToolError, ToolRegistry


def test_registers_read_only_project_inspection_tool() -> None:
    registry = ToolRegistry()
    register_project_inspection_tool(registry)
    descriptor = registry.get("workspace.inspect_project")
    assert descriptor.approval_required is False
    assert descriptor.effect.value == "WORKSPACE_WRITE"


def test_inventory_is_sorted_bounded_and_written_below_artifacts(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "b.py").write_text("print('b')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Example\n", encoding="utf-8")

    result = asyncio.run(
        inspect_project(
            {"workspace_root": str(tmp_path), "expected_artifact": "project-inventory.json"}
        )
    )

    target = tmp_path / result["path"]
    document = json.loads(target.read_text(encoding="utf-8"))
    assert [item["path"] for item in document["files"]] == ["README.md", "src/b.py"]
    assert all("sha256" in item and "preview" in item for item in document["files"])
    assert result["file_count"] == 2
    assert result["path"] == ".rad-agent-artifacts/project-inventory.json"


def test_ignores_secrets_dependencies_hidden_state_and_binary(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TOKEN=value\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "package.js").write_text("bad", encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"\x00\x01")
    (tmp_path / "config.py").write_text(
        "token = 'ghp_abcdefghijklmnopqrstuvwxyz1234567890'\n", encoding="utf-8"
    )
    (tmp_path / "main.py").write_text("answer = 42\n", encoding="utf-8")

    result = asyncio.run(
        inspect_project({"workspace_root": str(tmp_path), "expected_artifact": "inventory.json"})
    )
    document = json.loads((tmp_path / result["path"]).read_text(encoding="utf-8"))
    assert [item["path"] for item in document["files"]] == ["main.py"]
    assert document["excluded_count"] == 4


def test_rejects_symlinked_content(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-phase8.txt"
    outside.write_text("outside", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(outside)
    with pytest.raises(ToolError, match="symlink"):
        asyncio.run(
            inspect_project(
                {"workspace_root": str(tmp_path), "expected_artifact": "inventory.json"}
            )
        )


def _design_task(root: Path) -> TaskDefinition:
    return TaskDefinition(
        TaskId("design"),
        "mode.app_build.design",
        (),
        ActionEffect.WORKSPACE_WRITE,
        60,
        1,
        0,
        {"workspace_root": str(root), "expected_artifact": "architecture.md"},
    )


def test_context_revalidates_inventory_before_returning_bounded_source(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    asyncio.run(
        inspect_project({"workspace_root": str(tmp_path), "expected_artifact": "specification.md"})
    )
    context = ProjectInventoryContext().context_for(_design_task(tmp_path))
    assert context is not None
    assert context["inventory_file_count"] == 1
    assert context["files"][0]["path"] == "app.py"
    assert str(tmp_path) not in json.dumps(context)


def test_context_rejects_source_drift_before_model_use(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("value = 1\n", encoding="utf-8")
    asyncio.run(
        inspect_project({"workspace_root": str(tmp_path), "expected_artifact": "specification.md"})
    )
    source.write_text("value = 2\n", encoding="utf-8")
    with pytest.raises(ToolError, match="changed"):
        ProjectInventoryContext().context_for(_design_task(tmp_path))


def test_context_rejects_parent_replaced_by_symlink(tmp_path: Path) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("value = 1\n", encoding="utf-8")
    asyncio.run(
        inspect_project({"workspace_root": str(tmp_path), "expected_artifact": "specification.md"})
    )
    outside = tmp_path.parent / "phase8b-outside"
    outside.mkdir(exist_ok=True)
    (outside / "app.py").write_text("value = 1\n", encoding="utf-8")
    (source_dir / "app.py").unlink()
    source_dir.rmdir()
    source_dir.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ToolError, match="unsafe"):
        ProjectInventoryContext().context_for(_design_task(tmp_path))
