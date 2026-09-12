"""Bounded, read-only inspection for an operator-approved software project."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from nexus_os.domain import ActionEffect, TaskDefinition
from nexus_os.secrets import redact
from nexus_os.tools import ToolDescriptor, ToolError, ToolRegistry

_ARTIFACT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,239}$")
_INVENTORY_ARTIFACT = "project-inventory.json"
_EXCLUDED_DIRS = frozenset(
    {".git", ".hg", ".svn", ".rad-agent-artifacts", ".venv", "node_modules", "dist", "build"}
)
_SECRET_NAMES = re.compile(
    r"(^|[._-])(\.env|credentials?|secrets?|private[-_]?key|id_rsa|id_ed25519)([._-]|$)",
    re.IGNORECASE,
)
_SECRET_CONTENT = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
_MAX_FILES = 5_000
_MAX_FILE_BYTES = 256 * 1024
_MAX_TOTAL_BYTES = 20 * 1024 * 1024
_MAX_PREVIEW_BYTES = 8 * 1024
_MAX_OUTPUT_BYTES = 4 * 1024 * 1024
_MAX_CONTEXT_BYTES = 48 * 1024


class ProjectInventoryContext:
    """Revalidate and bound the Phase 8A inventory before model reasoning."""

    def context_for(self, task: TaskDefinition) -> Mapping[str, Any] | None:
        if task.kind == "mode.app_build.specification" or not task.kind.startswith(
            "mode.app_build."
        ):
            return None
        root_value = task.input.get("workspace_root")
        if not isinstance(root_value, str):
            raise ToolError("project context workspace is invalid")
        root = Path(root_value).resolve()
        artifact_root = root / ".rad-agent-artifacts"
        inventory = artifact_root / _INVENTORY_ARTIFACT
        if (
            not root.is_dir()
            or root.is_symlink()
            or artifact_root.is_symlink()
            or artifact_root.resolve().parent != root
            or inventory.is_symlink()
        ):
            raise ToolError("project context boundary is unsafe")
        try:
            raw = inventory.read_bytes()
        except OSError as exc:
            raise ToolError("verified project inventory is unavailable") from exc
        if not 1 <= len(raw) <= _MAX_OUTPUT_BYTES:
            raise ToolError("verified project inventory is invalid")
        try:
            document = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ToolError("verified project inventory is invalid") from exc
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != "1.0"
            or document.get("tool") != "workspace.inspect_project"
            or not isinstance(document.get("files"), list)
            or document.get("file_count") != len(document["files"])
        ):
            raise ToolError("verified project inventory is invalid")

        verified: list[dict[str, Any]] = []
        for item in document["files"]:
            verified.append(_verify_inventory_item(root, item))
        if [item["path"] for item in verified] != sorted(item["path"] for item in verified):
            raise ToolError("verified project inventory order is invalid")
        if len({item["path"] for item in verified}) != len(verified):
            raise ToolError("verified project inventory contains duplicate paths")

        selected: list[dict[str, Any]] = []
        context: dict[str, Any] = {
            "schema_version": "1.0",
            "inventory_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "files": selected,
            "inventory_file_count": len(verified),
            "context_truncated": False,
        }
        for item in verified:
            selected.append(item)
            if len(_canonical_bytes(context)) > _MAX_CONTEXT_BYTES:
                selected.pop()
                context["context_truncated"] = True
                break
        if len(_canonical_bytes(context)) > _MAX_CONTEXT_BYTES:
            raise ToolError("verified project context exceeds its prompt budget")
        return context


def _verify_inventory_item(root: Path, item: object) -> dict[str, Any]:
    expected = {"path", "bytes", "sha256", "preview", "preview_truncated"}
    if not isinstance(item, dict) or set(item) != expected:
        raise ToolError("verified project inventory file record is invalid")
    relative_value = item.get("path")
    if (
        not isinstance(relative_value, str)
        or not _ARTIFACT.fullmatch(relative_value)
        or relative_value.startswith("/")
        or ".." in Path(relative_value).parts
    ):
        raise ToolError("verified project inventory path is invalid")
    source = root / relative_value
    resolved_source = source.resolve()
    if (
        source.is_symlink()
        or resolved_source != source.absolute()
        or root not in resolved_source.parents
        or not source.is_file()
    ):
        raise ToolError("verified project source is missing or unsafe")
    try:
        body = source.read_bytes()
    except OSError as exc:
        raise ToolError("verified project source could not be read") from exc
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    try:
        preview = body[:_MAX_PREVIEW_BYTES].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError("verified project source encoding changed") from exc
    if (
        item.get("bytes") != len(body)
        or item.get("sha256") != digest
        or item.get("preview") != preview
        or item.get("preview_truncated") is not (len(body) > _MAX_PREVIEW_BYTES)
    ):
        raise ToolError("verified project source changed after inspection")
    return {
        "path": relative_value,
        "bytes": len(body),
        "sha256": digest,
        "preview": preview,
        "preview_truncated": len(body) > _MAX_PREVIEW_BYTES,
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def register_project_inspection_tool(registry: ToolRegistry) -> None:
    descriptor = ToolDescriptor(
        name="workspace.inspect_project",
        description="Create a bounded, read-only inventory of an approved software workspace.",
        effect=ActionEffect.WORKSPACE_WRITE,
        timeout_seconds=30,
        idempotent=True,
        approval_required=False,
        input_schema={
            "type": "object",
            "required": ["workspace_root", "expected_artifact"],
            "properties": {
                "workspace_root": {"type": "string", "minLength": 1, "maxLength": 4096},
                "expected_artifact": {
                    "type": "string",
                    "pattern": r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9][A-Za-z0-9._/-]{0,239}$",
                },
            },
            "additionalProperties": True,
        },
        output_schema={
            "type": "object",
            "required": ["path", "sha256", "bytes", "file_count", "excluded_count"],
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 4096},
                "sha256": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
                "bytes": {"type": "integer", "minimum": 1, "maximum": _MAX_OUTPUT_BYTES},
                "file_count": {"type": "integer", "minimum": 0, "maximum": _MAX_FILES},
                "excluded_count": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": False,
        },
    )
    registry.register(descriptor)
    registry.bind(descriptor.name, inspect_project)


async def inspect_project(payload: dict[str, Any]) -> dict[str, Any]:
    root_value = payload.get("workspace_root")
    artifact_value = payload.get("expected_artifact")
    if not isinstance(root_value, str) or not isinstance(artifact_value, str):
        raise ToolError("project inspection input is invalid")
    if not _ARTIFACT.fullmatch(artifact_value):
        raise ToolError("project inspection artifact is invalid")
    root = Path(root_value).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ToolError("approved workspace root must be an existing real directory")

    files: list[dict[str, Any]] = []
    excluded = 0
    total = 0
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        retained_dirs = []
        for name in sorted(directory_names):
            candidate = current_path / name
            if candidate.is_symlink():
                raise ToolError("project inspection rejects symlinked content")
            if name in _EXCLUDED_DIRS or name.startswith("."):
                excluded += 1
            else:
                retained_dirs.append(name)
        directory_names[:] = retained_dirs
        for name in sorted(file_names):
            candidate = current_path / name
            if candidate.is_symlink():
                raise ToolError("project inspection rejects symlinked content")
            relative = candidate.relative_to(root)
            if name.startswith(".") or _SECRET_NAMES.search(name):
                excluded += 1
                continue
            try:
                size = candidate.stat().st_size
            except OSError as exc:
                raise ToolError("project inspection could not stat a file") from exc
            if size > _MAX_FILE_BYTES:
                excluded += 1
                continue
            total += size
            if total > _MAX_TOTAL_BYTES or len(files) >= _MAX_FILES:
                raise ToolError("project inspection exceeds bounded workspace limits")
            try:
                body = candidate.read_bytes()
            except OSError as exc:
                raise ToolError("project inspection could not read a file") from exc
            if b"\x00" in body:
                excluded += 1
                continue
            try:
                preview = body[:_MAX_PREVIEW_BYTES].decode("utf-8")
            except UnicodeDecodeError:
                excluded += 1
                continue
            if redact(preview) != preview or _SECRET_CONTENT.search(preview):
                excluded += 1
                continue
            files.append(
                {
                    "path": relative.as_posix(),
                    "bytes": len(body),
                    "sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
                    "preview": preview,
                    "preview_truncated": len(body) > _MAX_PREVIEW_BYTES,
                }
            )

    files.sort(key=lambda item: item["path"])
    document = {
        "schema_version": "1.0",
        "tool": "workspace.inspect_project",
        "files": files,
        "file_count": len(files),
        "excluded_count": excluded,
        "total_bytes": sum(item["bytes"] for item in files),
    }
    body = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(body) > _MAX_OUTPUT_BYTES:
        raise ToolError("project inspection artifact is oversized")
    artifact_root = root / ".rad-agent-artifacts"
    artifact_root.mkdir(mode=0o700, exist_ok=True)
    if artifact_root.is_symlink() or artifact_root.resolve().parent != root:
        raise ToolError("project inspection artifact directory is unsafe")
    target = artifact_root / _INVENTORY_ARTIFACT
    if target.is_symlink():
        raise ToolError("project inspection artifact target is unsafe")
    if target.exists():
        if target.read_bytes() != body:
            raise ToolError("project inspection artifact already exists with different content")
    else:
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise ToolError("project inspection artifact could not be written") from exc
    return {
        "path": str(target.relative_to(root)),
        "sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "file_count": len(files),
        "excluded_count": excluded,
    }
