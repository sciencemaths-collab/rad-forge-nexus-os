import os

import pytest

from nexus_os.agent_server_cli import AgentServerCliError, load_factory, read_bootstrap_password


def test_password_file_requires_private_regular_single_line_file(tmp_path) -> None:
    path = tmp_path / "password"
    path.write_text("correct horse battery staple\n", encoding="utf-8")
    os.chmod(path, 0o600)
    assert read_bootstrap_password(path) == "correct horse battery staple"

    os.chmod(path, 0o644)
    with pytest.raises(AgentServerCliError, match="group or others"):
        read_bootstrap_password(path)


def test_factory_reference_fails_safely() -> None:
    assert callable(load_factory("nexus_os.agent_server_cli:parser"))
    with pytest.raises(AgentServerCliError, match="MODULE:FUNCTION"):
        load_factory("invalid")
    with pytest.raises(AgentServerCliError, match="could not be loaded"):
        load_factory("nexus_os.agent_server_cli:missing")
