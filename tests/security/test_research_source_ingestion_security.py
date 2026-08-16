import asyncio
import json

import pytest

from nexus_os.research_tools import ingest_local_research_sources
from nexus_os.tools import ToolError


def _manifest(path, source="paper.md"):  # type: ignore[no-untyped-def]
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "sources": [
                    {
                        "path": source,
                        "locator": "local:paper",
                        "retrieved_at": "2026-08-16T00:00:00Z",
                        "license_access": "Local test fixture",
                    }
                ],
            }
        )
    )


def _run(workspace):  # type: ignore[no-untyped-def]
    return asyncio.run(
        ingest_local_research_sources(
            {"workspace_root": str(workspace), "expected_artifact": "sources.json"}
        )
    )


def test_ingestion_rejects_traversal_symlinks_and_unsupported_types(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    sources = workspace / "research-sources"
    sources.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("outside")

    _manifest(sources / "manifest.json", "../outside.md")
    with pytest.raises(ToolError, match="path is invalid"):
        _run(workspace)

    _manifest(sources / "manifest.json", "paper.md")
    (sources / "paper.md").symlink_to(outside)
    with pytest.raises(ToolError, match="real file"):
        _run(workspace)

    (sources / "paper.md").unlink()
    (sources / "paper.pdf").write_bytes(b"not a supported parser")
    _manifest(sources / "manifest.json", "paper.pdf")
    with pytest.raises(ToolError, match="path is invalid"):
        _run(workspace)


def test_ingestion_rejects_workspace_and_nested_directory_symlinks(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    sources = workspace / "research-sources"
    sources.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "paper.md").write_text("outside")
    (sources / "linked").symlink_to(outside, target_is_directory=True)
    _manifest(sources / "manifest.json", "linked/paper.md")
    with pytest.raises(ToolError, match="parent directories must be real"):
        _run(workspace)

    alias = tmp_path / "workspace-alias"
    alias.symlink_to(workspace, target_is_directory=True)
    with pytest.raises(ToolError, match="workspace root"):
        _run(alias)


def test_ingestion_rejects_secret_like_oversized_and_conflicting_content(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    sources = workspace / "research-sources"
    sources.mkdir(parents=True)
    _manifest(sources / "manifest.json")
    paper = sources / "paper.md"
    paper.write_text("github_pat_abcdefghijklmnopqrstuvwxyz123456")
    with pytest.raises(ToolError, match="secret-like"):
        _run(workspace)

    paper.write_bytes(b"a" * (512 * 1024 + 1))
    with pytest.raises(ToolError, match="oversized"):
        _run(workspace)

    paper.write_text("safe source")
    _run(workspace)
    paper.write_text("changed source")
    with pytest.raises(ToolError, match="different content"):
        _run(workspace)
