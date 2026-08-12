"""Validated, canonical project configuration loading.

Configuration is untrusted input. This module performs no secret resolution and
no side effects beyond reading the explicitly supplied file.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import yaml
from jsonschema import Draft202012Validator, FormatChecker

MAX_CONFIG_BYTES = 1024 * 1024
ENV_PREFIX = "NEXUS__"
SECRET_REFERENCE_PREFIXES = ("env:", "vault:", "secret:")
_SOURCE_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "project.schema.json"


class ConfigError(ValueError):
    """A safe, user-facing configuration failure."""


class _NoAliasSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that also rejects aliases and anchors."""

    def compose_node(self, parent: yaml.Node | None, index: int) -> yaml.Node:
        if self.check_event(yaml.AliasEvent):  # type: ignore[no-untyped-call]
            raise ConfigError("YAML aliases are not allowed in project configuration")
        event = self.peek_event()  # type: ignore[no-untyped-call]
        if getattr(event, "anchor", None) is not None:
            raise ConfigError("YAML anchors are not allowed in project configuration")
        return cast(yaml.Node, super().compose_node(parent, index))


@dataclass(frozen=True, slots=True)
class LoadedConfig:
    """Immutable handle over a validated canonical configuration."""

    _data: Mapping[str, Any]
    canonical_json: str
    digest: str

    @property
    def data(self) -> Mapping[str, Any]:
        """Return a defensive, read-only top-level configuration mapping."""
        return MappingProxyType(copy.deepcopy(dict(self._data)))

    def redacted_manifest(self) -> dict[str, Any]:
        """Return a serializable manifest that contains no secret references."""
        manifest = copy.deepcopy(dict(self._data))
        manifest["secrets"] = {name: "<redacted-reference>" for name in manifest["secrets"]}
        for provider in manifest["providers"].values():
            if "credential" in provider:
                provider["credential"] = "<redacted-reference>"
        return manifest


def load_project_config(
    path: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
    max_bytes: int = MAX_CONFIG_BYTES,
) -> LoadedConfig:
    """Load, overlay, default, validate, and canonicalize a project config."""
    config_path = Path(path)
    raw = _read_bounded(config_path, max_bytes=max_bytes)
    document = _parse_document(raw, suffix=config_path.suffix.lower())
    if environ is not None:
        document = _apply_environment_overlays(document, environ)
    schema = _load_schema()
    _apply_defaults(document, schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise ConfigError(f"invalid project configuration at {location}: {first.message}")
    canonical_json = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = f"sha256:{hashlib.sha256(canonical_json.encode()).hexdigest()}"
    return LoadedConfig(MappingProxyType(document), canonical_json, digest)


def _read_bounded(path: Path, *, max_bytes: int) -> str:
    if max_bytes < 1:
        raise ConfigError("configuration size limit must be positive")
    try:
        if not path.is_file():
            raise ConfigError(f"configuration is not a regular file: {path}")
        size = path.stat().st_size
        if size > max_bytes:
            raise ConfigError(f"configuration exceeds {max_bytes} byte limit")
        return path.read_text(encoding="utf-8")
    except ConfigError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ConfigError(f"unable to read configuration: {path}") from exc


def _parse_document(raw: str, *, suffix: str) -> dict[str, Any]:
    try:
        if suffix == ".json":
            value = json.loads(raw)
        elif suffix in {".yaml", ".yml"}:
            loader = _NoAliasSafeLoader(raw)
            try:
                value = loader.get_single_data()
            finally:
                loader.dispose()  # type: ignore[no-untyped-call]
        else:
            raise ConfigError("project configuration must use .json, .yaml, or .yml")
    except ConfigError:
        raise
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ConfigError("project configuration is malformed") from exc
    if not isinstance(value, dict):
        raise ConfigError("project configuration root must be an object")
    if not all(isinstance(key, str) for key in value):
        raise ConfigError("project configuration keys must be strings")
    return value


def _load_schema() -> dict[str, Any]:
    try:
        schema_resource = files("nexus_os").joinpath("schemas/project.schema.json")
        try:
            raw_schema = schema_resource.read_text(encoding="utf-8")
        except OSError:
            # Editable source checkouts do not materialize wheel force-includes.
            raw_schema = _SOURCE_SCHEMA_PATH.read_text(encoding="utf-8")
        schema = cast(dict[str, Any], json.loads(raw_schema))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("packaged project schema is unavailable or invalid") from exc
    Draft202012Validator.check_schema(schema)
    return schema


def _apply_defaults(instance: dict[str, Any], schema: dict[str, Any]) -> None:
    for name, property_schema in schema.get("properties", {}).items():
        if name not in instance and "default" in property_schema:
            instance[name] = copy.deepcopy(property_schema["default"])
        value = instance.get(name)
        if isinstance(value, dict):
            _apply_defaults(value, property_schema)
    definitions = schema.get("$defs")
    providers = instance.get("providers")
    if isinstance(definitions, dict) and isinstance(providers, dict):
        provider_schema = definitions["providerBinding"]
        for provider in providers.values():
            if isinstance(provider, dict):
                _apply_defaults(provider, provider_schema)


def _apply_environment_overlays(
    document: dict[str, Any], environ: Mapping[str, str]
) -> dict[str, Any]:
    result = copy.deepcopy(document)
    for key in sorted(environ):
        if not key.startswith(ENV_PREFIX):
            continue
        path = [part.lower() for part in key[len(ENV_PREFIX) :].split("__") if part]
        if not path:
            raise ConfigError(f"invalid environment overlay name: {key}")
        cursor: dict[str, Any] = result
        for part in path[:-1]:
            value = cursor.get(part)
            if not isinstance(value, dict):
                raise ConfigError(f"environment overlay targets unknown object: {key}")
            cursor = value
        leaf = path[-1]
        if leaf not in cursor:
            raise ConfigError(f"environment overlay targets unknown key: {key}")
        try:
            overlay = yaml.safe_load(environ[key])
        except yaml.YAMLError as exc:
            raise ConfigError(f"environment overlay is malformed: {key}") from exc
        if path[-1] in {"credential", "secrets"} and isinstance(overlay, str):
            if not overlay.startswith(SECRET_REFERENCE_PREFIXES):
                raise ConfigError(f"environment overlay contains a literal secret: {key}")
        cursor[leaf] = overlay
    return result


def environment() -> Mapping[str, str]:
    """Return the process environment as a read-only mapping for explicit callers."""
    return MappingProxyType(dict(os.environ))
