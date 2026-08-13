import json
import os
from datetime import UTC, datetime

import pytest

from nexus_os.agent_model_config import (
    load_agent_model_config,
    resolve_agent_model_sync,
)
from nexus_os.local_agent_application import DevelopmentModelAuthorization
from nexus_os.model_qualification import ModelUse
from nexus_os.model_registry import ModelQualificationRegistry, ModelRegistryError
from nexus_os.rad_cli import RadCliError, doctor_local, parser, setup_local
from nexus_os.secrets import SecretResolver


class Transport:
    async def health(self, base_url, api_key, timeout_seconds):
        return True

    async def list_models(self, base_url, api_key, timeout_seconds):
        return ("local-model",)

    async def create_chat_completion(self, base_url, request, api_key, timeout_seconds):
        raise AssertionError("setup must not invoke inference")


def passwords():
    values = iter(("correct horse battery staple", "correct horse battery staple"))
    return lambda _prompt: next(values)


def probe(base_url, timeout_seconds):
    assert base_url == "http://127.0.0.1:11434/v1"
    assert timeout_seconds == 5
    return ("local-model",)


def test_setup_creates_private_valid_development_configuration(tmp_path) -> None:
    root = tmp_path / ".rad-agent"
    values = parser().parse_args(
        [
            "setup",
            "--config-dir",
            str(root),
            "--base-url",
            "http://127.0.0.1:11434/v1",
            "--model",
            "local-model",
        ]
    )
    result = setup_local(values, probe=probe, password_reader=passwords())
    assert result["status"] == "configured"
    assert result["qualified"] is False
    assert not (root.stat().st_mode & 0o077)
    assert not ((root / "operator-password").stat().st_mode & 0o077)
    assert load_agent_model_config(root / "models.yaml").selected == "local_default"

    healthy, checks = doctor_local(root, probe=probe)
    assert healthy
    assert {item["status"] for item in checks} == {"pass", "warning"}
    assert "UNQUALIFIED DEVELOPMENT MODE" in json.dumps(checks)


def test_setup_rejects_ambiguous_remote_and_unsafe_credential(tmp_path) -> None:
    ambiguous = parser().parse_args(["setup", "--config-dir", str(tmp_path / "one")])
    with pytest.raises(RadCliError, match="multiple model endpoints"):
        setup_local(
            ambiguous,
            probe=lambda _url, _timeout: ("one",),
            password_reader=passwords(),
        )

    remote = parser().parse_args(
        [
            "setup",
            "--config-dir",
            str(tmp_path / "two"),
            "--base-url",
            "https://api.example.com/v1",
        ]
    )
    with pytest.raises(RadCliError, match="loopback"):
        setup_local(remote, probe=probe, password_reader=passwords())

    literal = parser().parse_args(
        [
            "setup",
            "--config-dir",
            str(tmp_path / "three"),
            "--base-url",
            "http://127.0.0.1:11434/v1",
            "--model",
            "local-model",
            "--credential-ref",
            "literal-secret",
        ]
    )
    with pytest.raises(RadCliError, match="opaque"):
        setup_local(literal, probe=probe, password_reader=passwords())


def test_doctor_detects_unsafe_password_and_unavailable_model(tmp_path) -> None:
    root = tmp_path / ".rad-agent"
    values = parser().parse_args(
        [
            "setup",
            "--config-dir",
            str(root),
            "--base-url",
            "http://127.0.0.1:11434/v1",
            "--model",
            "local-model",
        ]
    )
    setup_local(values, probe=probe, password_reader=passwords())
    os.chmod(root / "operator-password", 0o644)
    healthy, checks = doctor_local(root, probe=lambda _url, _timeout: ())
    assert not healthy
    failures = {item["name"] for item in checks if item["status"] == "fail"}
    assert failures == {"password_file", "model_endpoint"}


def test_development_authorization_is_visibly_unqualified_and_proposal_only(
    tmp_path,
) -> None:
    subject = DevelopmentModelAuthorization()
    now = datetime.now(UTC)
    assert subject.active(at=now) == ()
    subject.authorize(
        provider_id="local_openai",
        model_id="local-model",
        adapter_version="1.0",
        use=ModelUse.CANDIDATE_SPECIFICATION,
        at=now,
    )
    with pytest.raises(ModelRegistryError, match="does not authorize"):
        subject.authorize(
            provider_id="local_openai",
            model_id="local-model",
            adapter_version="1.0",
            use=ModelUse.TOOL_SELECTION,
            at=now,
        )

    config = tmp_path / "models.yaml"
    config.write_text(
        "schema_version: '1.0'\nselected: local\nprofiles:\n  local:\n"
        "    type: local_openai\n    base_url: http://127.0.0.1:11434/v1\n"
        "    model: local-model\n",
        encoding="utf-8",
    )
    registry = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    resolved = resolve_agent_model_sync(
        load_agent_model_config(config),
        transport=Transport(),
        qualifications=registry,
        resolver=SecretResolver(),
        at=now,
        require_qualification=False,
    )
    assert resolved.model == "local-model"


@pytest.mark.parametrize(
    "arguments", [[], ["setup", "--help"], ["doctor", "--help"], ["serve", "--help"]]
)
def test_help_surfaces_do_not_require_a_control_client(arguments) -> None:
    with pytest.raises(SystemExit) as raised:
        parser().parse_args(arguments or ["--help"])
    assert raised.value.code == 0
