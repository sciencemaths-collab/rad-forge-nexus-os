"""Approval-gated Python verification commands with an audit sandbox."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from nexus_os.domain import ActionEffect
from nexus_os.tools import ToolDescriptor, ToolError, ToolRegistry

_COMMANDS = {
    ("python", "-m", "pytest", "-q", "tests/unit"),
    ("python", "-m", "pytest", "-q", "tests/integration"),
    ("python", "-m", "pytest", "-q", "tests/security"),
    ("python", "-m", "pytest", "-q", "tests/failure"),
}
_MAX_OUTPUT = 128 * 1024
_AUDITED_RUNNER = r"""
import os, runpy, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
module = sys.argv[2]
args = sys.argv[3:]
sys.path.insert(0, str(root))
def audit(event, values):
    blocked = {"socket.connect", "socket.bind", "socket.getaddrinfo",
               "subprocess.Popen", "os.system"}
    if event in blocked:
        raise PermissionError("RAD verification sandbox denied external effect")
    if event == "open" and values and isinstance(values[0], (str, bytes, os.PathLike)):
        mode = values[1] if len(values) > 1 else "r"
        if isinstance(mode, str) and any(flag in mode for flag in "wax+"):
            target = Path(values[0]).resolve()
            outside = target != root and root not in target.parents
            if target != Path(os.devnull).resolve() and outside:
                raise PermissionError("RAD verification sandbox denied external write")
sys.addaudithook(audit)
sys.argv = [module, *args]
runpy.run_module(module, run_name="__main__")
"""


def register_verification_command_tool(registry: ToolRegistry) -> None:
    descriptor = ToolDescriptor(
        name="workspace.run_python_verification",
        description="Run one exact allowlisted Python verification command without a shell.",
        effect=ActionEffect.SENSITIVE,
        timeout_seconds=180,
        idempotent=False,
        approval_required=True,
        input_schema={
            "type": "object",
            "required": ["workspace_root", "expected_artifact", "verification_command"],
            "properties": {
                "workspace_root": {"type": "string", "minLength": 1, "maxLength": 4096},
                "expected_artifact": {"type": "string", "minLength": 1, "maxLength": 240},
                "verification_command": {
                    "type": "array",
                    "minItems": 5,
                    "maxItems": 5,
                    "items": {"type": "string", "minLength": 1, "maxLength": 64},
                },
            },
            "additionalProperties": True,
        },
        output_schema={
            "type": "object",
            "required": ["path", "sha256", "exit_code", "passed", "output_truncated"],
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 4096},
                "sha256": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
                "exit_code": {"type": "integer", "minimum": 0, "maximum": 255},
                "passed": {"type": "boolean"},
                "output_truncated": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    )
    registry.register(descriptor)
    registry.bind(descriptor.name, run_python_verification)


async def run_python_verification(payload: dict[str, Any]) -> dict[str, Any]:
    root_value = payload.get("workspace_root")
    artifact_value = payload.get("expected_artifact")
    command_value = payload.get("verification_command")
    if (
        not isinstance(root_value, str)
        or not isinstance(artifact_value, str)
        or not isinstance(command_value, list)
        or not all(isinstance(item, str) for item in command_value)
        or tuple(command_value) not in _COMMANDS
        or "/" in artifact_value
        or ".." in artifact_value
    ):
        raise ToolError("verification command is not allowlisted")
    root = Path(root_value).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ToolError("verification workspace is unsafe")
    requested = root / command_value[-1]
    if not requested.is_dir() or requested.is_symlink() or root not in requested.resolve().parents:
        raise ToolError("verification target is unavailable or unsafe")
    argv = [
        sys.executable,
        "-I",
        "-B",
        "-c",
        _AUDITED_RUNNER,
        str(root),
        command_value[2],
        *command_value[3:],
    ]
    temporary_root = root / ".rad-agent-tmp"
    temporary_root.mkdir(mode=0o700, exist_ok=True)
    if temporary_root.is_symlink() or temporary_root.resolve().parent != root:
        raise ToolError("verification temporary boundary is unsafe")
    try:
        completed = subprocess.run(  # noqa: S603 - fixed interpreter and exact allowlisted argv
            argv,
            cwd=root,
            env={
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "TMPDIR": str(temporary_root),
            },
            capture_output=True,
            check=False,
            timeout=150,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError("verification command timed out") from exc
    combined = completed.stdout + completed.stderr
    truncated = len(combined) > _MAX_OUTPUT
    output = combined[:_MAX_OUTPUT].decode("utf-8", errors="replace")
    document = {
        "schema_version": "1.0",
        "tool": "workspace.run_python_verification",
        "command": command_value,
        "exit_code": completed.returncode,
        "passed": completed.returncode == 0,
        "output": output,
        "output_truncated": truncated,
    }
    body = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    artifact_root = root / ".rad-agent-artifacts"
    artifact_root.mkdir(mode=0o700, exist_ok=True)
    if artifact_root.is_symlink() or artifact_root.resolve().parent != root:
        raise ToolError("verification artifact boundary is unsafe")
    target = artifact_root / artifact_value
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(body)
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ToolError("verification result could not be written") from exc
    if completed.returncode != 0:
        raise ToolError("verification command failed")
    return {
        "path": str(target.relative_to(root)),
        "sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
        "exit_code": completed.returncode,
        "passed": True,
        "output_truncated": truncated,
    }
