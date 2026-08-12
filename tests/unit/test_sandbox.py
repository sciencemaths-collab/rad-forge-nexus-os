from __future__ import annotations

from pathlib import Path

import pytest

from nexus_os.sandbox import SandboxError, WorkspaceSandbox


def test_resolve_allows_declared_read_and_write_paths(tmp_path: Path) -> None:
    (tmp_path / "input.txt").write_text("data", encoding="utf-8")
    sandbox = WorkspaceSandbox(tmp_path, writable=("output",))

    assert sandbox.resolve("input.txt", operation="read") == tmp_path / "input.txt"
    assert sandbox.resolve("output/result.txt", operation="write") == tmp_path / "output/result.txt"


def test_write_outside_declared_prefix_is_denied(tmp_path: Path) -> None:
    sandbox = WorkspaceSandbox(tmp_path, writable=("output",))

    with pytest.raises(SandboxError, match="write scope"):
        sandbox.resolve("input.txt", operation="write")


def test_subprocess_environment_is_allowlisted_and_secret_free(tmp_path: Path) -> None:
    sandbox = WorkspaceSandbox(tmp_path, environment_allowlist=("PATH", "LANG"))

    result = sandbox.subprocess_environment(
        {"PATH": "/usr/bin", "LANG": "C", "API_TOKEN": "canary"}
    )

    assert result == {"LANG": "C", "PATH": "/usr/bin"}


def test_network_is_denied_by_default_and_exactly_allowlisted(tmp_path: Path) -> None:
    sandbox = WorkspaceSandbox(tmp_path, network_hosts=("api.example.test",))

    sandbox.authorize_host("api.example.test", port=443)
    with pytest.raises(SandboxError, match="network host"):
        sandbox.authorize_host("evil.example.test", port=443)
    with pytest.raises(SandboxError, match="port"):
        sandbox.authorize_host("api.example.test", port=0)
