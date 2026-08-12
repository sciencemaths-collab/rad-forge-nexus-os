"""Deny-by-default workspace, environment, and network authorization."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Literal

_HOST = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*$"
)
_ENVIRONMENT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_SENSITIVE_ENVIRONMENT = re.compile(
    r"(?:API[_-]?KEY|AUTH|CREDENTIAL|PASSWORD|PRIVATE[_-]?KEY|SECRET|TOKEN)", re.IGNORECASE
)


class SandboxError(ValueError):
    """Safe authorization failure at a sandbox boundary."""


class WorkspaceSandbox:
    """Pure authorization layer for one canonical, non-symlink workspace root."""

    def __init__(
        self,
        root: str | Path,
        *,
        writable: Sequence[str] = (),
        environment_allowlist: Sequence[str] = (),
        network_hosts: Sequence[str] = (),
    ) -> None:
        supplied_root = Path(root)
        if not supplied_root.is_dir():
            raise SandboxError("workspace root must be an existing directory")
        if supplied_root.is_symlink():
            raise SandboxError("workspace root must not be a symlink")
        self._root = supplied_root.resolve(strict=True)
        self._writable = tuple(self._validate_relative_prefix(item) for item in writable)
        environment_keys: set[str] = set()
        for key in environment_allowlist:
            if _ENVIRONMENT_KEY.fullmatch(key) is None or _SENSITIVE_ENVIRONMENT.search(key):
                raise SandboxError("subprocess environment allowlist contains an unsafe key")
            environment_keys.add(key)
        self._environment_allowlist = frozenset(environment_keys)
        hosts: set[str] = set()
        for host in network_hosts:
            normalized = host.lower()
            if _HOST.fullmatch(normalized) is None:
                raise SandboxError("network host allowlist contains an invalid host")
            hosts.add(normalized)
        self._network_hosts = frozenset(hosts)

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, path: str | Path, *, operation: Literal["read", "write"]) -> Path:
        relative = self._validate_relative_path(path)
        candidate = (self._root / relative).resolve(strict=False)
        if not candidate.is_relative_to(self._root):
            raise SandboxError("workspace path would escape the declared root")
        if operation == "read":
            if not candidate.exists():
                raise SandboxError("workspace read target does not exist")
        elif operation == "write":
            if not any(
                relative == prefix or relative.is_relative_to(prefix) for prefix in self._writable
            ):
                raise SandboxError("workspace path is outside the declared write scope")
        else:
            raise SandboxError("unsupported workspace operation")
        return candidate

    def subprocess_environment(self, source: Mapping[str, str]) -> Mapping[str, str]:
        """Copy only non-secret explicitly allowed variables into a read-only mapping."""
        selected = {
            key: source[key]
            for key in sorted(self._environment_allowlist)
            if key in source and isinstance(source[key], str)
        }
        return MappingProxyType(selected)

    def authorize_host(self, host: str, *, port: int) -> None:
        """Fail closed unless an exact normalized hostname and valid port are allowed."""
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise SandboxError("network port must be between 1 and 65535")
        if not isinstance(host, str) or host.lower() not in self._network_hosts:
            raise SandboxError("network host is not allowed")

    @staticmethod
    def _validate_relative_prefix(value: str) -> PurePosixPath:
        path = WorkspaceSandbox._validate_relative_path(value)
        if str(path) == ".":
            raise SandboxError("writable scope must not grant the entire workspace")
        return path

    @staticmethod
    def _validate_relative_path(value: str | Path) -> PurePosixPath:
        raw = str(value)
        if not raw or "\\" in raw or "\x00" in raw:
            raise SandboxError("workspace path is invalid")
        path = PurePosixPath(raw)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise SandboxError("workspace path must be normalized and relative")
        return path
