"""Validate and atomically materialize a version-bound RAD Agent project configuration."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from nexus_os.config import ConfigError, load_project_config

CURRENT_SCHEMA_VERSION = "1.0"


class MigrationError(ValueError):
    """Safe configuration migration failure."""


def migrate(source: Path, target: Path, from_version: str, to_version: str) -> None:
    """Write one validated canonical copy without overwriting an existing target."""
    if from_version != CURRENT_SCHEMA_VERSION or to_version != CURRENT_SCHEMA_VERSION:
        raise MigrationError("unsupported configuration migration path")
    loaded = load_project_config(source, environ={})
    if loaded.data.get("schema_version") != from_version:
        raise MigrationError("source configuration version does not match --from-version")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(loaded.canonical_json + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise MigrationError("migration target must be a new writable file") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely materialize a versioned RAD config")
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--from-version", required=True)
    parser.add_argument("--to-version", required=True)
    values = parser.parse_args()
    try:
        migrate(values.source, values.target, values.from_version, values.to_version)
    except (ConfigError, MigrationError) as exc:
        parser.exit(2, f"configuration migration failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
