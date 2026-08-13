import json

import pytest

from nexus_os.agent_model_config import AgentModelConfigError, load_agent_model_config
from nexus_os.rad_cli import models_local, parser, setup_local


def passwords():
    values = iter(("correct horse battery staple", "correct horse battery staple"))
    return lambda _prompt: next(values)


@pytest.mark.parametrize(
    ("port", "provider"),
    [(11434, "ollama"), (1234, "lm_studio"), (8080, "local_openai")],
)
def test_setup_identifies_supported_local_provider(tmp_path, port, provider) -> None:
    root = tmp_path / provider
    url = f"http://127.0.0.1:{port}/v1"
    values = parser().parse_args(
        [
            "setup",
            "--config-dir",
            str(root),
            "--base-url",
            url,
            "--model",
            "reference-model",
        ]
    )
    result = setup_local(
        values,
        probe=lambda base_url, _timeout: (
            ("reference-model",) if base_url == url else ()
        ),
        password_reader=passwords(),
    )
    assert result["provider"] == provider
    profile = load_agent_model_config(root / "models.yaml").profiles["local_default"]
    assert profile.provider_type == provider
    assert profile.public_dict()["type"] == provider


def test_models_list_redacts_credential_and_test_reports_discovery(tmp_path) -> None:
    root = tmp_path / "agent"
    url = "http://127.0.0.1:11434/v1"
    values = parser().parse_args(
        [
            "setup",
            "--config-dir",
            str(root),
            "--base-url",
            url,
            "--model",
            "reference-model",
            "--credential-ref",
            "env:OLLAMA_API_KEY",
        ]
    )
    setup_local(
        values,
        probe=lambda _url, _timeout: ("reference-model",),
        password_reader=passwords(),
    )

    healthy, listed = models_local(root, test_connection=False)
    assert healthy
    assert listed["profiles"][0]["credential"] == "<redacted-reference>"
    assert "OLLAMA_API_KEY" not in json.dumps(listed)

    healthy, tested = models_local(
        root,
        test_connection=True,
        probe=lambda _url, _timeout: ("reference-model", "second-model"),
    )
    assert healthy
    assert tested["connection"]["provider"] == "ollama"
    assert tested["connection"]["status"] == "pass"
    assert tested["connection"]["discovered_models"] == [
        "reference-model",
        "second-model",
    ]


def test_models_test_fails_closed_when_selected_model_disappears(tmp_path) -> None:
    root = tmp_path / "agent"
    url = "http://127.0.0.1:1234/v1"
    values = parser().parse_args(
        [
            "setup",
            "--config-dir",
            str(root),
            "--base-url",
            url,
            "--model",
            "reference-model",
        ]
    )
    setup_local(
        values,
        probe=lambda _url, _timeout: ("reference-model",),
        password_reader=passwords(),
    )
    healthy, tested = models_local(root, test_connection=True, probe=lambda _url, _timeout: ())
    assert not healthy
    assert tested["connection"]["status"] == "fail"


def test_provider_mismatch_and_unsupported_profile_fail_closed(tmp_path) -> None:
    url = "http://127.0.0.1:11434/v1"
    values = parser().parse_args(
        [
            "setup",
            "--config-dir",
            str(tmp_path / "mismatch"),
            "--provider",
            "lm_studio",
            "--base-url",
            url,
            "--model",
            "reference-model",
        ]
    )
    with pytest.raises(ValueError, match="does not match"):
        setup_local(
            values,
            probe=lambda _url, _timeout: ("reference-model",),
            password_reader=passwords(),
        )

    path = tmp_path / "models.yaml"
    path.write_text(
        "schema_version: '1.0'\nselected: cloud\nprofiles:\n  cloud:\n"
        "    type: arbitrary_cloud\n    base_url: http://127.0.0.1:8080/v1\n"
        "    model: reference-model\n",
        encoding="utf-8",
    )
    with pytest.raises(AgentModelConfigError, match="unsupported"):
        load_agent_model_config(path)
