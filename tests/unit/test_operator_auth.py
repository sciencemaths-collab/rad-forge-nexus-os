import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from nexus_os.operator_auth import OperatorAuthenticator, OperatorAuthError

NOW = datetime.now(UTC)
PASSWORD = "correct horse battery staple"  # noqa: S105 - inert local test fixture


def test_bootstrap_login_authenticate_revoke_and_no_plaintext_at_rest(tmp_path) -> None:
    path = tmp_path / "operator.sqlite"
    subject = OperatorAuthenticator(path)
    assert not subject.is_bootstrapped()
    subject.bootstrap(PASSWORD)
    assert subject.is_bootstrapped()

    issued = subject.login(PASSWORD, now=NOW)
    assert issued.identity.actor_id == "local-owner"
    assert issued.identity.human is True
    assert subject.authenticate(issued.token) == issued.identity
    subject.revoke(issued.token)
    assert subject.authenticate(issued.token) is None

    row = (
        sqlite3.connect(path)
        .execute("SELECT salt, password_hash, scopes_json FROM local_operators")
        .fetchone()
    )
    assert row is not None and PASSWORD not in path.read_bytes().decode(errors="ignore")
    assert len(row[0]) == 16 and len(row[1]) == 32
    subject.close()


def test_wrong_password_duplicate_bootstrap_and_naive_time_fail_closed(tmp_path) -> None:
    subject = OperatorAuthenticator(tmp_path / "operator.sqlite")
    subject.bootstrap(PASSWORD)
    with pytest.raises(OperatorAuthError, match="already bootstrapped"):
        subject.bootstrap("another secure password")
    with pytest.raises(OperatorAuthError, match="credentials are invalid"):
        subject.login("definitely not the password", now=NOW)
    with pytest.raises(OperatorAuthError, match="timezone-aware UTC"):
        subject.login(PASSWORD, now=datetime.now())
    subject.close()


def test_session_limit_and_configuration_bounds(tmp_path) -> None:
    subject = OperatorAuthenticator(
        tmp_path / "operator.sqlite", session_ttl=timedelta(minutes=1), max_sessions=1
    )
    subject.bootstrap(PASSWORD)
    subject.login(PASSWORD, now=NOW)
    with pytest.raises(OperatorAuthError, match="session limit"):
        subject.login(PASSWORD, now=NOW)
    subject.close()

    with pytest.raises(OperatorAuthError, match="session_ttl"):
        OperatorAuthenticator(tmp_path / "bad.sqlite", session_ttl=timedelta(seconds=59))
