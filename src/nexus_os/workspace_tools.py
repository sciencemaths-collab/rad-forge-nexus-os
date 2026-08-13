"""Built-in least-privilege workspace artifact tool for the reference runtime."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from nexus_os.domain import ActionEffect
from nexus_os.tools import ToolDescriptor, ToolError, ToolRegistry

_ARTIFACT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,239}$")
_MAX_ARTIFACT_BYTES = 1024 * 1024


def register_workspace_artifact_tool(registry: ToolRegistry) -> None:
    descriptor = ToolDescriptor(
        name="workspace.write_artifact",
        description=(
            "Write one deterministic, non-executable JSON artifact under the approved "
            "workspace artifacts directory."
        ),
        effect=ActionEffect.WORKSPACE_WRITE,
        timeout_seconds=10,
        idempotent=True,
        approval_required=False,
        input_schema={
            "type": "object",
            "required": ["workspace_root", "expected_artifact"],
            "properties": {
                "workspace_root": {"type": "string", "minLength": 1, "maxLength": 4096},
                "expected_artifact": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 240,
                    "pattern": r"^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))[A-Za-z0-9][A-Za-z0-9._/-]{0,239}$",
                },
            },
            "additionalProperties": True,
        },
        output_schema={
            "type": "object",
            "required": ["path", "sha256", "bytes", "created"],
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 4096},
                "sha256": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
                "bytes": {"type": "integer", "minimum": 1, "maximum": _MAX_ARTIFACT_BYTES},
                "created": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    )
    registry.register(descriptor)
    registry.bind(descriptor.name, write_workspace_artifact)


async def write_workspace_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    root_value = payload.get("workspace_root")
    artifact_value = payload.get("expected_artifact")
    if not isinstance(root_value, str) or not isinstance(artifact_value, str):
        raise ToolError("workspace artifact input is invalid")
    if (
        not _ARTIFACT.fullmatch(artifact_value)
        or artifact_value.startswith("/")
        or ".." in Path(artifact_value).parts
    ):
        raise ToolError("workspace artifact path is invalid")
    root = Path(root_value).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ToolError("approved workspace root must be an existing real directory")
    artifact_root = root / ".rad-agent-artifacts"
    artifact_root.mkdir(mode=0o700, exist_ok=True)
    if artifact_root.is_symlink() or artifact_root.resolve().parent != root:
        raise ToolError("workspace artifact directory is unsafe")
    target = artifact_root / artifact_value
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    resolved_parent = target.parent.resolve()
    if resolved_parent != artifact_root.resolve() and artifact_root.resolve() not in resolved_parent.parents:
        raise ToolError("workspace artifact escapes the approved root")
    if target.is_symlink():
        raise ToolError("workspace artifact target is unsafe")

    document = {
        "schema_version": "1.0",
        "tool": "workspace.write_artifact",
        "task_input": {key: value for key, value in payload.items() if key != "workspace_root"},
    }
    body = (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode()
    if not 1 <= len(body) <= _MAX_ARTIFACT_BYTES:
        raise ToolError("workspace artifact content is oversized")
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    relative = str(target.relative_to(root))
    if target.exists():
        try:
            existing = target.read_bytes()
        except OSError as exc:
            raise ToolError("workspace artifact could not be verified") from exc
        if existing != body:
            raise ToolError("workspace artifact already exists with different content")
        return {"path": relative, "sha256": digest, "bytes": len(body), "created": False}

    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            temporary = target
        raise ToolError("workspace artifact could not be written") from exc
    return {"path": relative, "sha256": digest, "bytes": len(body), "created": True}
