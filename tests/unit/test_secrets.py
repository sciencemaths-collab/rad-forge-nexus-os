from __future__ import annotations

import json

import pytest

from nexus_os.secrets import (
    SecretError,
    SecretReference,
    SecretResolver,
    redact,
    secret_scope,
)


def test_secret_reference_accepts_only_supported_opaque_references() -> None:
    reference = SecretReference.parse("env:NEXUS_TEST_KEY")

    assert reference.scheme == "env"
    assert reference.locator == "NEXUS_TEST_KEY"
    assert str(reference) == "env:NEXUS_TEST_KEY"

    for invalid in ("plaintext", "env:", "file:/tmp/key", "ENV:KEY", "env:../KEY"):
        with pytest.raises(SecretError):
            SecretReference.parse(invalid)


def test_resolution_is_explicit_and_value_is_nonserializable() -> None:
    resolver = SecretResolver(environment={"NEXUS_TEST_KEY": "canary-value"})

    with secret_scope(resolver, SecretReference.parse("env:NEXUS_TEST_KEY")) as secret:
        assert secret.reveal() == "canary-value"
        assert repr(secret) == "<ResolvedSecret redacted>"
        assert str(secret) == "<redacted>"
        with pytest.raises(TypeError):
            json.dumps({"credential": secret})

    with pytest.raises(SecretError, match="closed"):
        secret.reveal()


def test_missing_or_unsupported_backend_fails_safely() -> None:
    resolver = SecretResolver(environment={})

    with pytest.raises(SecretError, match="unavailable"):
        resolver.resolve(SecretReference.parse("env:MISSING"))
    with pytest.raises(SecretError, match="not configured"):
        resolver.resolve(SecretReference.parse("vault:team/provider"))


def test_redaction_is_recursive_and_does_not_mutate_input() -> None:
    payload = {
        "authorization": "Bearer abcdefghijklmnopqrstuvwxyz",
        "nested": [{"api_key": "value"}, "canary-value", "safe"],
        "reference": "env:NEXUS_TEST_KEY",
    }

    result = redact(payload, exact_values={"canary-value"})

    assert result == {
        "authorization": "<redacted>",
        "nested": [{"api_key": "<redacted>"}, "<redacted>", "safe"],
        "reference": "<redacted-reference>",
    }
    assert payload["nested"][0]["api_key"] == "value"


def test_redaction_handles_cycles_and_bounds_depth() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic

    assert redact(cyclic) == {"self": "<redacted-cycle>"}

    value: object = "leaf"
    for _ in range(40):
        value = [value]
    with pytest.raises(SecretError, match="depth"):
        redact(value, max_depth=16)
