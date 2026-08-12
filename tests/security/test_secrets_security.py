from __future__ import annotations

import pickle

import pytest

from nexus_os.secrets import SecretError, SecretReference, SecretResolver, redact


def test_resolved_secret_cannot_be_copied_or_pickled() -> None:
    secret = SecretResolver(environment={"KEY": "secret-canary"}).resolve(
        SecretReference.parse("env:KEY")
    )
    try:
        with pytest.raises(TypeError):
            pickle.dumps(secret)
    finally:
        secret.close()


def test_secret_value_never_appears_in_resolution_error() -> None:
    secret = SecretResolver(environment={"KEY": "secret-canary"}).resolve(
        SecretReference.parse("env:KEY")
    )
    secret.close()

    with pytest.raises(SecretError) as caught:
        secret.reveal()

    assert "secret-canary" not in str(caught.value)


def test_format_and_key_redaction_cover_common_credential_shapes() -> None:
    payload = {
        "password": "hunter2",
        "token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
        "ordinary": "not-sensitive",
        "url": "https://user:pass@example.test/path",
    }

    result = redact(payload)

    assert result == {
        "password": "<redacted>",
        "token": "<redacted>",
        "ordinary": "not-sensitive",
        "url": "<redacted>",
    }
