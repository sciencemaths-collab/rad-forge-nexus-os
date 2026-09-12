import asyncio
import json
from pathlib import Path

import pytest

from nexus_os.domain import ActionEffect
from nexus_os.tools import ToolError, ToolRegistry
from nexus_os.verification_commands import (
    register_verification_command_tool,
    run_python_verification,
)


def _payload(root: Path, command: list[str]) -> dict[str, object]:
    return {
        "workspace_root": str(root),
        "expected_artifact": "unit-tests.json",
        "verification_command": command,
    }


def test_verification_tool_is_sensitive_approval_gated_and_no_shell() -> None:
    registry = ToolRegistry()
    register_verification_command_tool(registry)
    descriptor = registry.get("workspace.run_python_verification")
    assert descriptor.effect is ActionEffect.SENSITIVE
    assert descriptor.approval_required is True


def test_runs_exact_allowlisted_pytest_and_records_output(tmp_path: Path) -> None:
    tests = tmp_path / "tests/unit"
    tests.mkdir(parents=True)
    (tests / "test_ok.py").write_text("def test_ok():\n    assert 2 + 2 == 4\n", encoding="utf-8")
    result = asyncio.run(
        run_python_verification(_payload(tmp_path, ["python", "-m", "pytest", "-q", "tests/unit"]))
    )
    document = json.loads((tmp_path / result["path"]).read_text(encoding="utf-8"))
    assert document["passed"] is True
    assert document["exit_code"] == 0
    assert "1 passed" in document["output"]


def test_rejects_shell_arbitrary_modules_and_missing_targets(tmp_path: Path) -> None:
    for command in (
        ["sh", "-c", "echo", "x", "tests/unit"],
        ["python", "-m", "http.server", "-q", "tests/unit"],
        ["python", "-m", "pytest", "-q", "tests/unit"],
    ):
        with pytest.raises(ToolError):
            asyncio.run(run_python_verification(_payload(tmp_path, command)))


def test_audit_sandbox_blocks_test_network_and_external_writes(tmp_path: Path) -> None:
    tests = tmp_path / "tests/unit"
    tests.mkdir(parents=True)
    outside = tmp_path.parent / "rad-verification-escape.txt"
    outside.unlink(missing_ok=True)
    (tests / "test_escape.py").write_text(
        "from pathlib import Path\n"
        f"def test_escape():\n    Path({str(outside)!r}).write_text('escape')\n",
        encoding="utf-8",
    )
    with pytest.raises(ToolError, match="failed"):
        asyncio.run(
            run_python_verification(
                _payload(tmp_path, ["python", "-m", "pytest", "-q", "tests/unit"])
            )
        )
    assert not outside.exists()
