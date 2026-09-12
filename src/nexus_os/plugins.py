"""Signed, bounded, inert-by-default RAD plugin package lifecycle."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import sqlite3
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_ID = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.-]{2,127}@[0-9]+\.[0-9]+\.[0-9]+$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_PERMISSIONS = frozenset(
    {"workspace.read", "workspace.write", "network", "secrets", "external.action"}
)
_MAX_PACKAGE = 55 * 1024 * 1024
_MAX_PAYLOAD = 50 * 1024 * 1024
_MAX_MANIFEST = 64 * 1024


class PluginError(ValueError):
    """Safe plugin package, trust, permission, or lifecycle rejection."""


@dataclass(frozen=True, slots=True)
class PluginRecord:
    plugin_id: str
    version: str
    publisher_id: str
    state: str
    permissions: tuple[str, ...]
    capabilities: tuple[str, ...]
    package_digest: str
    installed_at: datetime
    installed_by: str
    payload_path: Path
    qualification_digest: str | None

    def public_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "version": self.version,
            "publisher_id": self.publisher_id,
            "state": self.state,
            "permissions": list(self.permissions),
            "capabilities": list(self.capabilities),
            "package_digest": self.package_digest,
            "installed_at": _timestamp(self.installed_at),
            "installed_by": self.installed_by,
            "qualification_digest": self.qualification_digest,
            "execution_authorized": False,
        }


class PluginStore:
    """Atomic registry and managed payload storage for verified plugin packages."""

    def __init__(self, root: Path, *, rad_version: str) -> None:
        self.root = root.resolve()
        self.rad_version = rad_version
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self._payloads = self.root / "payloads"
        self._payloads.mkdir(mode=0o700, exist_ok=True)
        self._db = sqlite3.connect(self.root / "plugins.sqlite3", isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS plugins (
              plugin_id TEXT NOT NULL, version TEXT NOT NULL, publisher_id TEXT NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('DISABLED','ENABLED')),
              manifest_json TEXT NOT NULL, package_digest TEXT NOT NULL UNIQUE,
              payload_path TEXT NOT NULL, installed_at TEXT NOT NULL, installed_by TEXT NOT NULL,
              PRIMARY KEY(plugin_id, version)
            );
            CREATE TABLE IF NOT EXISTS plugin_events (
              sequence INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
              actor TEXT NOT NULL, action TEXT NOT NULL, plugin_id TEXT NOT NULL,
              version TEXT NOT NULL, package_digest TEXT NOT NULL
            );
            """
        )

    def install(
        self,
        package: Path,
        trust_store: Path,
        *,
        approved_permissions: Iterable[str],
        installed_by: str,
        installed_at: datetime,
        qualification_attestation: Path | None = None,
    ) -> PluginRecord:
        _utc(installed_at)
        actor = _actor(installed_by)
        approved = frozenset(approved_permissions)
        if not approved <= _PERMISSIONS:
            raise PluginError("approved plugin permissions are invalid")
        manifest, payload, package_digest = _verify_package(package, trust_store)
        required = frozenset(manifest["permissions"])
        if approved != required:
            raise PluginError("exact plugin permission approval is required")
        if not _compatible(self.rad_version, manifest["rad_version"]):
            raise PluginError("plugin is incompatible with this RAD version")
        expected_attestation = manifest["qualification"]["attestation_sha256"]
        if manifest["qualification"]["required"]:
            if qualification_attestation is None:
                raise PluginError("plugin qualification attestation is required")
            observed = _file_digest(qualification_attestation, _MAX_PACKAGE)
            if observed != expected_attestation:
                raise PluginError("plugin qualification attestation digest mismatch")
        elif expected_attestation is not None or qualification_attestation is not None:
            raise PluginError("plugin qualification declaration is inconsistent")
        destination_dir = self._payloads / manifest["plugin_id"] / manifest["version"]
        destination = destination_dir / manifest["payload"]["filename"]
        if destination.exists():
            raise PluginError("plugin version is already installed")
        destination_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        temporary = destination_dir / ".payload.tmp"
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            canonical = _canonical(manifest).decode()
            self._db.execute("BEGIN IMMEDIATE")
            self._db.execute(
                "INSERT INTO plugins VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    manifest["plugin_id"],
                    manifest["version"],
                    manifest["publisher_id"],
                    "DISABLED",
                    canonical,
                    package_digest,
                    str(destination),
                    _timestamp(installed_at),
                    actor,
                ),
            )
            self._event(
                "INSTALL",
                manifest["plugin_id"],
                manifest["version"],
                package_digest,
                actor,
                installed_at,
            )
            self._db.execute("COMMIT")
        except (OSError, sqlite3.Error) as exc:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            shutil.rmtree(destination_dir, ignore_errors=True)
            raise PluginError("plugin installation failed atomically") from exc
        return self.get(manifest["plugin_id"], manifest["version"])

    def enable(self, plugin_id: str, version: str, *, actor: str, at: datetime) -> PluginRecord:
        return self._state(plugin_id, version, "ENABLED", actor, at)

    def disable(self, plugin_id: str, version: str, *, actor: str, at: datetime) -> PluginRecord:
        return self._state(plugin_id, version, "DISABLED", actor, at)

    def uninstall(self, plugin_id: str, version: str, *, actor: str, at: datetime) -> None:
        _utc(at)
        user = _actor(actor)
        record = self.get(plugin_id, version)
        if record.state != "DISABLED":
            raise PluginError("plugin must be disabled before uninstall")
        payload = Path(record.payload_path)
        tombstone = payload.with_name(".uninstalling")
        try:
            os.replace(payload, tombstone)
        except OSError as exc:
            raise PluginError("plugin managed payload is unavailable") from exc
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute(
                "DELETE FROM plugins WHERE plugin_id=? AND version=?", (plugin_id, version)
            )
            self._event("UNINSTALL", plugin_id, version, record.package_digest, user, at)
            self._db.execute("COMMIT")
            tombstone.unlink()
            payload.parent.rmdir()
        except (OSError, sqlite3.Error) as exc:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
                os.replace(tombstone, payload)
            raise PluginError("plugin uninstall failed") from exc

    def get(self, plugin_id: str, version: str) -> PluginRecord:
        row = self._db.execute(
            "SELECT * FROM plugins WHERE plugin_id=? AND version=?", (plugin_id, version)
        ).fetchone()
        if row is None:
            raise PluginError("plugin version is not installed")
        return self._record(row)

    def list(self) -> tuple[PluginRecord, ...]:
        rows = self._db.execute("SELECT * FROM plugins ORDER BY plugin_id, version").fetchall()
        return tuple(self._record(row) for row in rows)

    def events(self) -> tuple[dict[str, Any], ...]:
        rows = self._db.execute("SELECT * FROM plugin_events ORDER BY sequence").fetchall()
        return tuple(
            {
                "sequence": row[0],
                "occurred_at": row[1],
                "actor": row[2],
                "action": row[3],
                "plugin_id": row[4],
                "version": row[5],
                "package_digest": row[6],
            }
            for row in rows
        )

    def close(self) -> None:
        self._db.close()

    def _record(self, row: tuple[Any, ...]) -> PluginRecord:
        manifest = json.loads(row[4])
        payload = Path(row[6])
        try:
            payload.relative_to(self._payloads)
        except ValueError as exc:
            raise PluginError("plugin managed payload path is invalid") from exc
        if _file_digest(payload, _MAX_PAYLOAD) != manifest["payload"]["sha256"]:
            raise PluginError("plugin managed payload integrity verification failed")
        return PluginRecord(
            row[0],
            row[1],
            row[2],
            row[3],
            tuple(manifest["permissions"]),
            tuple(manifest["capabilities"]),
            row[5],
            _parse_time(row[7]),
            row[8],
            payload,
            manifest["qualification"]["attestation_sha256"],
        )

    def _state(
        self, plugin_id: str, version: str, state: str, actor: str, at: datetime
    ) -> PluginRecord:
        _utc(at)
        user = _actor(actor)
        record = self.get(plugin_id, version)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            if state == "ENABLED":
                self._db.execute(
                    "UPDATE plugins SET state='DISABLED' WHERE plugin_id=? AND state='ENABLED'",
                    (plugin_id,),
                )
            self._db.execute(
                "UPDATE plugins SET state=? WHERE plugin_id=? AND version=?",
                (state, plugin_id, version),
            )
            self._event(state, plugin_id, version, record.package_digest, user, at)
            self._db.execute("COMMIT")
        except sqlite3.Error as exc:
            self._db.execute("ROLLBACK")
            raise PluginError("plugin lifecycle transition failed") from exc
        return self.get(plugin_id, version)

    def _event(
        self, action: str, plugin_id: str, version: str, digest: str, actor: str, at: datetime
    ) -> None:
        self._db.execute(
            "INSERT INTO plugin_events(occurred_at,actor,action,plugin_id,version,package_digest) "
            "VALUES(?,?,?,?,?,?)",
            (_timestamp(at), actor, action, plugin_id, version, digest),
        )


def _verify_package(package: Path, trust_store: Path) -> tuple[dict[str, Any], bytes, str]:
    if not package.is_file() or package.is_symlink() or package.stat().st_size > _MAX_PACKAGE:
        raise PluginError("plugin package is invalid or oversized")
    package_digest = _file_digest(package, _MAX_PACKAGE)
    try:
        with zipfile.ZipFile(package) as archive:
            names = archive.namelist()
            if (
                len(names) != 3
                or len(set(names)) != 3
                or "manifest.json" not in names
                or "signature.ed25519" not in names
            ):
                raise PluginError("plugin package members are invalid")
            if any(_unsafe_member(item) for item in archive.infolist()):
                raise PluginError("plugin package contains an unsafe member")
            manifest_bytes = archive.read("manifest.json")
            if len(manifest_bytes) > _MAX_MANIFEST:
                raise PluginError("plugin manifest is oversized")
            manifest = json.loads(manifest_bytes, object_pairs_hook=_unique)
            _manifest(manifest)
            payload_name = manifest["payload"]["filename"]
            if set(names) != {"manifest.json", "signature.ed25519", payload_name}:
                raise PluginError("plugin payload member does not match manifest")
            payload = archive.read(payload_name)
            signature = archive.read("signature.ed25519")
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise PluginError("plugin package could not be read") from exc
    if (
        len(payload) != manifest["payload"]["size_bytes"]
        or _digest(payload) != manifest["payload"]["sha256"]
    ):
        raise PluginError("plugin payload integrity verification failed")
    if len(payload) > _MAX_PAYLOAD or len(signature) != 64:
        raise PluginError("plugin package content is outside bounds")
    key = _trusted_key(trust_store, manifest["publisher_id"])
    try:
        key.verify(signature, _canonical(manifest))
    except InvalidSignature as exc:
        raise PluginError("plugin signature verification failed") from exc
    return manifest, payload, package_digest


def _manifest(value: object) -> None:
    fields = {
        "schema_version",
        "plugin_id",
        "version",
        "publisher_id",
        "rad_version",
        "payload",
        "permissions",
        "capabilities",
        "qualification",
    }
    if not isinstance(value, dict) or set(value) != fields or value["schema_version"] != "1.0":
        raise PluginError("plugin manifest fields are invalid")
    if (
        not _valid_id(value["plugin_id"])
        or not _valid_id(value["publisher_id"])
        or not _valid_version(value["version"])
    ):
        raise PluginError("plugin manifest identity is invalid")
    compatibility = value["rad_version"]
    if (
        not isinstance(compatibility, dict)
        or set(compatibility) != {"minimum", "maximum_exclusive"}
        or not all(isinstance(compatibility[x], str) for x in compatibility)
    ):
        raise PluginError("plugin RAD compatibility is invalid")
    payload = value["payload"]
    if (
        not isinstance(payload, dict)
        or set(payload) != {"filename", "sha256", "size_bytes"}
        or not isinstance(payload["filename"], str)
        or not _FILENAME.fullmatch(payload["filename"])
        or not isinstance(payload["sha256"], str)
        or not _DIGEST.fullmatch(payload["sha256"])
        or isinstance(payload["size_bytes"], bool)
        or not isinstance(payload["size_bytes"], int)
        or not 1 <= payload["size_bytes"] <= _MAX_PAYLOAD
    ):
        raise PluginError("plugin payload declaration is invalid")
    permissions, capabilities = value["permissions"], value["capabilities"]
    if (
        not isinstance(permissions, list)
        or len(set(permissions)) != len(permissions)
        or not set(permissions) <= _PERMISSIONS
    ):
        raise PluginError("plugin permissions are invalid")
    if (
        not isinstance(capabilities, list)
        or len(capabilities) > 64
        or len(set(capabilities)) != len(capabilities)
        or any(not isinstance(x, str) or not _CAPABILITY.fullmatch(x) for x in capabilities)
    ):
        raise PluginError("plugin capabilities are invalid")
    qualification = value["qualification"]
    if (
        not isinstance(qualification, dict)
        or set(qualification) != {"required", "attestation_sha256"}
        or not isinstance(qualification["required"], bool)
        or (
            qualification["attestation_sha256"] is not None
            and (
                not isinstance(qualification["attestation_sha256"], str)
                or not _DIGEST.fullmatch(qualification["attestation_sha256"])
            )
        )
    ):
        raise PluginError("plugin qualification declaration is invalid")


def _trusted_key(path: Path, publisher_id: str) -> Ed25519PublicKey:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
        if (
            not isinstance(value, dict)
            or set(value) != {"schema_version", "publishers"}
            or value["schema_version"] != "1.0"
            or not isinstance(value["publishers"], dict)
        ):
            raise PluginError("plugin trust store is invalid")
        encoded = value["publishers"].get(publisher_id)
        if not isinstance(encoded, str):
            raise PluginError("plugin publisher is not trusted")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) != 32:
            raise PluginError("plugin publisher key is invalid")
        return Ed25519PublicKey.from_public_bytes(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, PluginError):
            raise
        raise PluginError("plugin trust store could not be read") from exc


def _compatible(current: str, bounds: Mapping[str, Any]) -> bool:
    try:
        return (
            _version_tuple(bounds["minimum"])
            <= _version_tuple(current)
            < _version_tuple(bounds["maximum_exclusive"])
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PluginError("plugin RAD compatibility is invalid") from exc


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise ValueError
    return tuple(int(item) for item in match.groups())  # type: ignore[return-value]


def _unsafe_member(info: zipfile.ZipInfo) -> bool:
    path = Path(info.filename)
    mode = info.external_attr >> 16
    return (
        path.is_absolute()
        or ".." in path.parts
        or info.is_dir()
        or (mode & 0o170000) == 0o120000
        or info.file_size > _MAX_PACKAGE
    )


def _file_digest(path: Path, limit: int) -> str:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
        raise PluginError("plugin input file is invalid or oversized")
    return _digest(path.read_bytes())


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise PluginError("plugin JSON contains duplicate keys")
        result[key] = value
    return result


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _valid_version(value: object) -> bool:
    return isinstance(value, str) and _VERSION.fullmatch(value) is not None


def _actor(value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise PluginError("plugin lifecycle actor is invalid")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _utc(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise PluginError("plugin lifecycle time must be timezone-aware UTC")


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
