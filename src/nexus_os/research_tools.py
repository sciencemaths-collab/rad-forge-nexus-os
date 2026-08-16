"""Least-privilege local research source ingestion."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from nexus_os.domain import ActionEffect
from nexus_os.secrets import redact
from nexus_os.tools import ToolDescriptor, ToolError, ToolRegistry

_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,239}$")
_MAX_MANIFEST_BYTES = 64 * 1024
_MAX_SOURCE_BYTES = 512 * 1024
_MAX_TOTAL_SOURCE_BYTES = 768 * 1024
_MAX_ARTIFACT_BYTES = 1024 * 1024
_MAX_SOURCES = 32
_EXTRACTOR_VERSION = "rad.local-text/1.0"
_LINE_EXTRACTOR_VERSION = "rad.source-lines/1.0"


def register_local_research_source_tool(registry: ToolRegistry) -> None:
    """Register deterministic local-source ingestion without network or arbitrary paths."""
    descriptor = ToolDescriptor(
        name="research.ingest_local_sources",
        description=(
            "Ingest manifest-declared UTF-8 research text from the approved workspace and "
            "write a deterministic source-provenance artifact."
        ),
        effect=ActionEffect.WORKSPACE_WRITE,
        timeout_seconds=10,
        idempotent=False,
        approval_required=False,
        input_schema={
            "type": "object",
            "required": ["workspace_root", "expected_artifact"],
            "properties": {
                "workspace_root": {"type": "string", "minLength": 1, "maxLength": 4096},
                "expected_artifact": {"const": "sources.json"},
            },
            "additionalProperties": True,
        },
        output_schema={
            "type": "object",
            "required": [
                "path",
                "sha256",
                "bytes",
                "created",
                "source_count",
                "source_set_digest",
            ],
            "properties": {
                "path": {"const": ".rad-agent-artifacts/sources.json"},
                "sha256": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
                "bytes": {"type": "integer", "minimum": 1, "maximum": _MAX_ARTIFACT_BYTES},
                "created": {"type": "boolean"},
                "source_count": {"type": "integer", "minimum": 1, "maximum": _MAX_SOURCES},
                "source_set_digest": {
                    "type": "string",
                    "pattern": "^sha256:[a-f0-9]{64}$",
                },
            },
            "additionalProperties": False,
        },
    )
    registry.register(descriptor)
    registry.bind(descriptor.name, ingest_local_research_sources)


def register_local_research_extraction_tool(registry: ToolRegistry) -> None:
    """Register deterministic, line-addressable extraction from sources.json."""
    descriptor = ToolDescriptor(
        name="research.extract_source_lines",
        description=(
            "Create exact, line-addressable extractions from the verified local source artifact."
        ),
        effect=ActionEffect.WORKSPACE_WRITE,
        timeout_seconds=10,
        idempotent=False,
        approval_required=False,
        input_schema={
            "type": "object",
            "required": ["workspace_root", "expected_artifact"],
            "properties": {
                "workspace_root": {"type": "string", "minLength": 1, "maxLength": 4096},
                "expected_artifact": {"const": "extractions.json"},
            },
            "additionalProperties": True,
        },
        output_schema={
            "type": "object",
            "required": ["path", "sha256", "bytes", "created", "source_count", "line_count"],
            "properties": {
                "path": {"const": ".rad-agent-artifacts/extractions.json"},
                "sha256": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
                "bytes": {"type": "integer", "minimum": 1, "maximum": _MAX_ARTIFACT_BYTES},
                "created": {"type": "boolean"},
                "source_count": {"type": "integer", "minimum": 1, "maximum": _MAX_SOURCES},
                "line_count": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": False,
        },
    )
    registry.register(descriptor)
    registry.bind(descriptor.name, extract_local_source_lines)


async def extract_local_source_lines(payload: dict[str, Any]) -> dict[str, Any]:
    root_value = payload.get("workspace_root")
    if not isinstance(root_value, str) or payload.get("expected_artifact") != "extractions.json":
        raise ToolError("research source extraction input is invalid")
    supplied_root = Path(root_value)
    if supplied_root.is_symlink():
        raise ToolError("approved workspace root must be an existing real directory")
    root = supplied_root.resolve()
    if not root.is_dir():
        raise ToolError("approved workspace root must be an existing real directory")
    source_path = _artifact_target(root, "sources.json", create=False)
    source_body = _read_bounded(source_path, _MAX_ARTIFACT_BYTES, "research source artifact")
    try:
        source_document = json.loads(source_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolError("research source artifact must be valid UTF-8 JSON") from exc
    if not valid_source_artifact(source_document):
        raise ToolError("research source artifact provenance is invalid")
    extractions = []
    line_count = 0
    for source in source_document["sources"]:
        lines = [
            {"line": number, "text": text, "text_digest": _digest(text.encode())}
            for number, text in enumerate(source["text"].splitlines(), start=1)
        ]
        line_count += len(lines)
        extractions.append(
            {
                "source_id": source["source_id"],
                "locator": source["locator"],
                "extracted_text_digest": source["extracted_text_digest"],
                "line_count": len(lines),
                "lines": lines,
            }
        )
    document = {
        "schema_version": "1.0",
        "tool": "research.extract_source_lines",
        "extractor_version": _LINE_EXTRACTOR_VERSION,
        "sources_artifact_digest": _digest(source_body),
        "source_set_digest": source_document["source_set_digest"],
        "source_count": len(extractions),
        "line_count": line_count,
        "extraction_set_digest": _digest(_canonical(extractions)),
        "extractions": extractions,
    }
    body = _canonical(document) + b"\n"
    if len(body) > _MAX_ARTIFACT_BYTES:
        raise ToolError("research extraction artifact is oversized")
    target = _artifact_target(root, "extractions.json")
    created = _write_once(target, body)
    return {
        "path": ".rad-agent-artifacts/extractions.json",
        "sha256": _digest(body),
        "bytes": len(body),
        "created": created,
        "source_count": len(extractions),
        "line_count": line_count,
    }


async def ingest_local_research_sources(payload: dict[str, Any]) -> dict[str, Any]:
    root_value = payload.get("workspace_root")
    if not isinstance(root_value, str) or payload.get("expected_artifact") != "sources.json":
        raise ToolError("research source ingestion input is invalid")
    supplied_root = Path(root_value)
    if supplied_root.is_symlink():
        raise ToolError("approved workspace root must be an existing real directory")
    root = supplied_root.resolve()
    if not root.is_dir():
        raise ToolError("approved workspace root must be an existing real directory")
    source_root = root / "research-sources"
    if not source_root.is_dir() or source_root.is_symlink():
        raise ToolError("research source directory must be an existing real directory")
    source_root_resolved = source_root.resolve()
    if source_root_resolved.parent != root:
        raise ToolError("research source directory escapes the approved workspace")

    manifest_path = source_root / "manifest.json"
    manifest_bytes = _read_bounded(manifest_path, _MAX_MANIFEST_BYTES, "research manifest")
    manifest = _manifest(manifest_bytes)
    manifest_digest = _digest(manifest_bytes)
    records: list[dict[str, Any]] = []
    total_source_bytes = 0
    seen_paths: set[str] = set()
    seen_locators: set[str] = set()
    for entry in manifest["sources"]:
        relative = entry["path"]
        locator = entry["locator"]
        if relative in seen_paths or locator in seen_locators:
            raise ToolError("research manifest source paths and locators must be unique")
        seen_paths.add(relative)
        seen_locators.add(locator)
        source_path = source_root / relative
        _validate_source_path(source_root, source_root_resolved, source_path, relative)
        raw = _read_bounded(source_path, _MAX_SOURCE_BYTES, "research source")
        total_source_bytes += len(raw)
        if total_source_bytes > _MAX_TOTAL_SOURCE_BYTES:
            raise ToolError("research source collection is oversized")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError("research source must be UTF-8 text") from exc
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if "\x00" in normalized or redact(normalized) != normalized:
            raise ToolError("research source contains unsafe or secret-like content")
        suffix = source_path.suffix.lower()
        content_digest = _digest(raw)
        text_digest = _digest(normalized.encode("utf-8"))
        source_id = _digest(f"{locator}\n{content_digest}".encode())
        records.append(
            {
                "source_id": source_id,
                "locator": locator,
                "retrieved_at": entry["retrieved_at"],
                "license_access": entry["license_access"],
                "media_type": "text/markdown" if suffix == ".md" else "text/plain",
                "content_digest": content_digest,
                "extracted_text_digest": text_digest,
                "bytes": len(raw),
                "characters": len(normalized),
                "lines": len(normalized.splitlines()),
                "text": normalized,
                "provenance": {
                    "workspace_path": f"research-sources/{relative}",
                    "manifest_digest": manifest_digest,
                    "extractor_version": _EXTRACTOR_VERSION,
                },
            }
        )
    source_set_digest = _digest(_canonical(records))
    document = {
        "schema_version": "1.0",
        "tool": "research.ingest_local_sources",
        "extractor_version": _EXTRACTOR_VERSION,
        "manifest_digest": manifest_digest,
        "source_count": len(records),
        "total_source_bytes": total_source_bytes,
        "source_set_digest": source_set_digest,
        "sources": records,
    }
    body = _canonical(document) + b"\n"
    if len(body) > _MAX_ARTIFACT_BYTES:
        raise ToolError("research source artifact is oversized")
    target = _artifact_target(root, "sources.json")
    created = _write_once(target, body)
    return {
        "path": ".rad-agent-artifacts/sources.json",
        "sha256": _digest(body),
        "bytes": len(body),
        "created": created,
        "source_count": len(records),
        "source_set_digest": source_set_digest,
    }


def _manifest(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolError("research manifest must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict) or set(value) != {"schema_version", "sources"}:
        raise ToolError("research manifest fields are invalid")
    sources = value.get("sources")
    if value.get("schema_version") != "1.0" or not isinstance(sources, list):
        raise ToolError("research manifest version or sources are invalid")
    if not 1 <= len(sources) <= _MAX_SOURCES or redact(value) != value:
        raise ToolError("research manifest is empty, oversized, or unsafe")
    for entry in sources:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "locator",
            "retrieved_at",
            "license_access",
        }:
            raise ToolError("research manifest source fields are invalid")
        _manifest_entry(entry)
    return value


def _manifest_entry(entry: dict[str, Any]) -> None:
    relative = entry.get("path")
    locator = entry.get("locator")
    retrieved_at = entry.get("retrieved_at")
    access = entry.get("license_access")
    if (
        not isinstance(relative, str)
        or not _PATH.fullmatch(relative)
        or relative.startswith("/")
        or ".." in Path(relative).parts
        or Path(relative).suffix.lower() not in {".md", ".txt"}
    ):
        raise ToolError("research manifest source path is invalid")
    if not isinstance(locator, str) or not 1 <= len(locator) <= 2048:
        raise ToolError("research manifest locator is invalid")
    if not isinstance(access, str) or not 1 <= len(access) <= 1000:
        raise ToolError("research manifest access note is invalid")
    if not isinstance(retrieved_at, str) or not _utc_timestamp(retrieved_at):
        raise ToolError("research manifest retrieval time is invalid")


def _utc_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (
        value.endswith("Z")
        and parsed.tzinfo is not None
        and parsed.utcoffset() == UTC.utcoffset(parsed)
    )


def _read_bounded(path: Path, limit: int, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ToolError(f"{label} must be a real file")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            size = os.fstat(stream.fileno()).st_size
            if not 1 <= size <= limit:
                raise ToolError(f"{label} is empty or oversized")
            body = stream.read(limit + 1)
    except OSError as exc:
        raise ToolError(f"{label} could not be read") from exc
    if len(body) != size or len(body) > limit:
        raise ToolError(f"{label} changed during reading or is oversized")
    return body


def _validate_source_path(
    source_root: Path, source_root_resolved: Path, source_path: Path, relative: str
) -> None:
    current = source_root
    for part in Path(relative).parts[:-1]:
        current /= part
        if current.is_symlink():
            raise ToolError("research source parent directories must be real")
    if source_path.is_symlink():
        raise ToolError("research source must be a real file")
    resolved = source_path.resolve()
    if resolved == source_root_resolved or source_root_resolved not in resolved.parents:
        raise ToolError("research source escapes the approved source directory")


def _artifact_target(root: Path, name: str, *, create: bool = True) -> Path:
    artifact_root = root / ".rad-agent-artifacts"
    if create:
        artifact_root.mkdir(mode=0o700, exist_ok=True)
    if artifact_root.is_symlink() or artifact_root.resolve().parent != root:
        raise ToolError("research artifact directory is unsafe")
    target = artifact_root / name
    if target.is_symlink():
        raise ToolError("research source artifact target is unsafe")
    return target


def valid_source_artifact(value: object) -> bool:
    """Verify nested source provenance before extraction or download."""
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        return False
    sources, manifest_digest = value.get("sources"), value.get("manifest_digest")
    if not isinstance(sources, list) or not 1 <= len(sources) <= _MAX_SOURCES:
        return False
    if value.get("source_count") != len(sources) or not _is_digest(manifest_digest):
        return False
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("text"), str):
            return False
        locator, content_digest, provenance = (
            source.get("locator"),
            source.get("content_digest"),
            source.get("provenance"),
        )
        if (
            not isinstance(locator, str)
            or not _is_digest(content_digest)
            or not isinstance(provenance, dict)
        ):
            return False
        if provenance.get("manifest_digest") != manifest_digest:
            return False
        if source.get("extracted_text_digest") != _digest(source["text"].encode()):
            return False
        if source.get("source_id") != _digest(f"{locator}\n{content_digest}".encode()):
            return False
    return value.get("source_set_digest") == _digest(_canonical(sources))


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"sha256:[a-f0-9]{64}", value))


def _write_once(target: Path, body: bytes) -> bool:
    if target.exists():
        try:
            if target.read_bytes() == body:
                return False
        except OSError as exc:
            raise ToolError("research source artifact could not be verified") from exc
        raise ToolError("research source artifact already exists with different content")
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
            pass
        raise ToolError("research source artifact could not be written") from exc
    return True


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
