from __future__ import annotations

import os
from pathlib import Path

import pytest

from nexus_os.sandbox import SandboxError, WorkspaceSandbox


@pytest.mark.parametrize("path", ("../escape", "a/../../escape", "/workspace-escape", ""))
def test_traversal_absolute_and_empty_paths_are_rejected(tmp_path: Path, path: str) -> None:
    sandbox = WorkspaceSandbox(tmp_path)

    with pytest.raises(SandboxError):
        sandbox.resolve(path, operation="read")


def test_symlink_escape_is_rejected_for_read_and_write(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    os.symlink(outside, tmp_path / "link", target_is_directory=True)
    sandbox = WorkspaceSandbox(tmp_path, writable=("link",))

    with pytest.raises(SandboxError, match="escape"):
        sandbox.resolve("link/secret.txt", operation="read")
    with pytest.raises(SandboxError, match="escape"):
        sandbox.resolve("link/new.txt", operation="write")


def test_symlinked_workspace_root_is_rejected(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    os.symlink(actual, alias, target_is_directory=True)

    with pytest.raises(SandboxError, match="symlink"):
        WorkspaceSandbox(alias)


def test_invalid_writable_scope_and_host_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(SandboxError):
        WorkspaceSandbox(tmp_path, writable=("../outside",))
    with pytest.raises(SandboxError):
        WorkspaceSandbox(tmp_path, network_hosts=("https://example.test",))
