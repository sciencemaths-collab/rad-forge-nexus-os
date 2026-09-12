"""Approval-gated, digest-bound text changes with local rollback evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from nexus_os.domain import ActionEffect
from nexus_os.secrets import redact
from nexus_os.tools import ToolDescriptor, ToolError, ToolRegistry

_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,239}$")
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_SECRET_NAME = re.compile(
    r"(?:^|[._-])(?:\.env|credentials?|secrets?|private[-_]?key)(?:[._-]|$)", re.I
)
_SECRET_CONTENT = re.compile(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})")
_MAX_FILES = 32
_MAX_FILE_BYTES = 256 * 1024
_MAX_TOTAL_BYTES = 1024 * 1024


def register_controlled_editing_tool(registry: ToolRegistry) -> None:
    descriptor = ToolDescriptor(
        name="workspace.apply_text_changes",
        description="Apply exact digest-bound text replacements and preserve rollback evidence.",
        effect=ActionEffect.SENSITIVE,
        timeout_seconds=30,
        idempotent=True,
        approval_required=True,
        input_schema={
            "type": "object",
            "required": ["workspace_root", "reasoned_artifact", "reasoned_artifact_digest"],
            "properties": {
                "workspace_root": {"type": "string", "minLength": 1, "maxLength": 4096},
                "reasoned_artifact_digest": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
                "reasoned_artifact": {"type": "object"},
            },
            "additionalProperties": True,
        },
        output_schema={
            "type": "object",
            "required": ["path", "sha256", "files_changed", "created"],
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 4096},
                "sha256": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
                "files_changed": {"type": "integer", "minimum": 1, "maximum": _MAX_FILES},
                "created": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    )
    registry.register(descriptor)
    registry.bind(descriptor.name, apply_text_changes)


async def apply_text_changes(payload: dict[str, Any]) -> dict[str, Any]:
    root_value = payload.get("workspace_root")
    artifact = payload.get("reasoned_artifact")
    artifact_digest = payload.get("reasoned_artifact_digest")
    if (
        not isinstance(root_value, str)
        or not isinstance(artifact, dict)
        or not isinstance(artifact_digest, str)
        or not _DIGEST.fullmatch(artifact_digest)
        or _artifact_digest(artifact) != artifact_digest
    ):
        raise ToolError("controlled edit input is invalid")
    changes = artifact.get("file_changes")
    if not isinstance(changes, list) or not 1 <= len(changes) <= _MAX_FILES:
        raise ToolError("controlled edit requires bounded file changes")
    root = Path(root_value).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ToolError("controlled edit workspace is unsafe")

    prepared: list[tuple[Path, bytes | None, bytes]] = []
    total = 0
    seen: set[str] = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"path", "expected_sha256", "content"}:
            raise ToolError("controlled edit change is invalid")
        relative, expected, content = change["path"], change["expected_sha256"], change["content"]
        if (
            not isinstance(relative, str)
            or not _PATH.fullmatch(relative)
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or relative in seen
            or any(part.startswith(".") for part in Path(relative).parts)
            or _SECRET_NAME.search(Path(relative).name)
            or not isinstance(content, str)
            or not content
            or "\x00" in content
            or redact(content) != content
            or _SECRET_CONTENT.search(content)
        ):
            raise ToolError("controlled edit change is unsafe")
        seen.add(relative)
        replacement = content.encode()
        total += len(replacement)
        if len(replacement) > _MAX_FILE_BYTES or total > _MAX_TOTAL_BYTES:
            raise ToolError("controlled edit content exceeds limits")
        target = root / relative
        _safe_parent(root, target)
        if target.is_symlink():
            raise ToolError("controlled edit target is unsafe")
        prior: bytes | None
        if target.exists():
            if (
                not target.is_file()
                or not isinstance(expected, str)
                or not _DIGEST.fullmatch(expected)
            ):
                raise ToolError("controlled edit existing target contract is invalid")
            prior = target.read_bytes()
            if _sha(prior) != expected:
                raise ToolError("controlled edit target changed after proposal")
        else:
            if expected is not None:
                raise ToolError("controlled edit new target contract is invalid")
            prior = None
        prepared.append((target, prior, replacement))

    rollback_root = root / ".rad-agent-artifacts" / "rollback"
    rollback_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if rollback_root.is_symlink() or root not in rollback_root.resolve().parents:
        raise ToolError("controlled edit rollback boundary is unsafe")
    rollback = rollback_root / f"{artifact_digest.removeprefix('sha256:')}.json"
    summary = root / ".rad-agent-artifacts" / "implementation"
    final_digests = {str(target.relative_to(root)): _sha(body) for target, _, body in prepared}
    if rollback.exists():
        if summary.is_file() and all(
            target.is_file() and _sha(target.read_bytes()) == _sha(body)
            for target, _, body in prepared
        ):
            return {
                "path": str(summary.relative_to(root)),
                "sha256": _sha(summary.read_bytes()),
                "files_changed": len(prepared),
                "created": False,
            }
        raise ToolError("controlled edit replay conflicts with workspace state")

    rollback_document = {
        "schema_version": "1.0",
        "tool": "workspace.apply_text_changes",
        "reasoned_artifact_digest": artifact_digest,
        "files": [
            {
                "path": str(target.relative_to(root)),
                "original_content": None if prior is None else prior.decode("utf-8"),
                "original_sha256": None if prior is None else _sha(prior),
                "applied_sha256": final_digests[str(target.relative_to(root))],
            }
            for target, prior, _ in prepared
        ],
    }
    rollback_body = (
        json.dumps(rollback_document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    summary_body = (
        json.dumps(
            {
                "schema_version": "1.0",
                "tool": "workspace.apply_text_changes",
                "reasoned_artifact_digest": artifact_digest,
                "rollback_path": str(rollback.relative_to(root)),
                "files": [
                    {"path": path, "applied_sha256": digest}
                    for path, digest in sorted(final_digests.items())
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    temporaries: list[tuple[Path, Path]] = []
    try:
        for target, _, replacement in prepared:
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _safe_parent(root, target)
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.rad-tmp")
            temporary.write_bytes(replacement)
            os.chmod(temporary, 0o600)
            temporaries.append((target, temporary))
        rollback.write_bytes(rollback_body)
        os.chmod(rollback, 0o600)
        for target, temporary in temporaries:
            os.replace(temporary, target)
        summary.write_bytes(summary_body)
        os.chmod(summary, 0o600)
    except (OSError, UnicodeDecodeError) as exc:
        for target, prior, _ in prepared:
            try:
                if prior is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(prior)
            except OSError:
                pass
        rollback.unlink(missing_ok=True)
        summary.unlink(missing_ok=True)
        for _, temporary in temporaries:
            temporary.unlink(missing_ok=True)
        raise ToolError("controlled edit could not be applied atomically") from exc
    return {
        "path": str(summary.relative_to(root)),
        "sha256": _sha(summary_body),
        "files_changed": len(prepared),
        "created": True,
    }


def _safe_parent(root: Path, target: Path) -> None:
    existing = target.parent
    while not existing.exists() and existing != root:
        existing = existing.parent
    if existing.is_symlink() or (
        existing.resolve() != root and root not in existing.resolve().parents
    ):
        raise ToolError("controlled edit path escapes the workspace")


def _artifact_digest(artifact: dict[str, Any]) -> str:
    encoded = json.dumps(
        artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return _sha(encoded)


def _sha(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()
