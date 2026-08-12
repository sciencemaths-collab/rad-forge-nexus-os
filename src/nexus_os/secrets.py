"""Opaque secret references, short-lived resolution, and safe redaction."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping, Set
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, NoReturn

_REFERENCE = re.compile(r"^(env|vault|secret):([A-Za-z0-9][A-Za-z0-9_.\-/]{0,254})$")
_ENV_LOCATOR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,254}$")
_SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(api[_-]?key|authorization|credential|password|private[_-]?key|secret|token)(?:$|[_-])",
    re.IGNORECASE,
)
_CREDENTIAL_FORMATS = (
    re.compile(r"^Bearer\s+\S{8,}$", re.IGNORECASE),
    re.compile(r"^(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})$"),
    re.compile(r"^https?://[^/@:\s]+:[^/@\s]+@", re.IGNORECASE),
)
_REDACTED = "<redacted>"


class SecretError(ValueError):
    """Safe secret-boundary failure that never includes resolved material."""


@dataclass(frozen=True, slots=True)
class SecretReference:
    """Validated opaque pointer to a secret backend entry."""

    scheme: str
    locator: str

    @classmethod
    def parse(cls, value: str) -> SecretReference:
        if not isinstance(value, str):
            raise SecretError("secret reference must be a string")
        match = _REFERENCE.fullmatch(value)
        if match is None or ".." in match.group(2).split("/"):
            raise SecretError("secret reference must use a supported opaque reference")
        scheme, locator = match.groups()
        if scheme == "env" and _ENV_LOCATOR.fullmatch(locator) is None:
            raise SecretError("environment secret reference is invalid")
        return cls(scheme=scheme, locator=locator)

    def __str__(self) -> str:
        return f"{self.scheme}:{self.locator}"


class ResolvedSecret:
    """Best-effort zeroizable, deliberately non-serializable secret value."""

    __slots__ = ("_buffer", "_closed")

    def __init__(self, value: str) -> None:
        if not value:
            raise SecretError("resolved secret is unavailable")
        self._buffer = bytearray(value.encode("utf-8"))
        self._closed = False

    def reveal(self) -> str:
        if self._closed:
            raise SecretError("resolved secret is closed")
        return self._buffer.decode("utf-8")

    def close(self) -> None:
        if not self._closed:
            for index in range(len(self._buffer)):
                self._buffer[index] = 0
            self._buffer.clear()
            self._closed = True

    def __enter__(self) -> ResolvedSecret:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "<ResolvedSecret redacted>"

    def __str__(self) -> str:
        return _REDACTED

    def __reduce__(self) -> NoReturn:
        raise TypeError("resolved secrets cannot be serialized")


SecretBackend = Callable[[str], str | None]


class SecretResolver:
    """Explicit resolver with no implicit access to process-global state."""

    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        backends: Mapping[str, SecretBackend] | None = None,
    ) -> None:
        self._environment = dict(environment or {})
        self._backends = dict(backends or {})

    def resolve(self, reference: SecretReference) -> ResolvedSecret:
        if reference.scheme == "env":
            value = self._environment.get(reference.locator)
        else:
            backend = self._backends.get(reference.scheme)
            if backend is None:
                raise SecretError(f"secret backend '{reference.scheme}' is not configured")
            try:
                value = backend(reference.locator)
            except Exception as exc:
                raise SecretError("secret backend resolution failed") from exc
        if value is None or not isinstance(value, str) or not value:
            raise SecretError("resolved secret is unavailable")
        return ResolvedSecret(value)


@contextmanager
def secret_scope(
    resolver: SecretResolver, reference: SecretReference
) -> Iterator[ResolvedSecret]:
    """Resolve a value for one lexical scope and close it on every exit path."""
    secret = resolver.resolve(reference)
    try:
        yield secret
    finally:
        secret.close()


def redact(value: Any, *, exact_values: Set[str] = frozenset(), max_depth: int = 32) -> Any:
    """Return a recursively redacted copy suitable for logs and evidence."""
    if max_depth < 1:
        raise SecretError("redaction depth limit must be positive")
    safe_exact = frozenset(item for item in exact_values if item)
    return _redact(value, exact_values=safe_exact, depth=0, max_depth=max_depth, seen=set())


def _redact(
    value: Any,
    *,
    exact_values: frozenset[str],
    depth: int,
    max_depth: int,
    seen: set[int],
    sensitive: bool = False,
) -> Any:
    if depth > max_depth:
        raise SecretError("redaction depth limit exceeded")
    if isinstance(value, ResolvedSecret):
        return _REDACTED
    if isinstance(value, SecretReference):
        return "<redacted-reference>"
    if isinstance(value, str):
        if sensitive or value in exact_values:
            return _REDACTED
        if _REFERENCE.fullmatch(value):
            return "<redacted-reference>"
        if any(pattern.search(value) for pattern in _CREDENTIAL_FORMATS):
            return _REDACTED
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in seen:
            return "<redacted-cycle>"
        seen.add(identity)
        try:
            return {
                str(key): _redact(
                    item,
                    exact_values=exact_values,
                    depth=depth + 1,
                    max_depth=max_depth,
                    seen=seen,
                    sensitive=bool(_SENSITIVE_KEY.search(str(key))),
                )
                for key, item in value.items()
            }
        finally:
            seen.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in seen:
            return "<redacted-cycle>"
        seen.add(identity)
        try:
            return [
                _redact(
                    item,
                    exact_values=exact_values,
                    depth=depth + 1,
                    max_depth=max_depth,
                    seen=seen,
                )
                for item in value
            ]
        finally:
            seen.remove(identity)
    return _REDACTED
