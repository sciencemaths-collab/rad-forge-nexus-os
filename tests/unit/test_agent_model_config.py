from datetime import UTC, datetime

import pytest

from nexus_os.agent_model_config import (
    AgentModelConfigError,
    load_agent_model_config,
    resolve_agent_model_sync,
)
from nexus_os.model_registry import ModelQualificationRegistry
from nexus_os.secrets import SecretResolver
from tests.unit.test_model_registry import REGISTERED_AT, attestation

NOW = datetime(2026, 8, 13, 13, tzinfo=UTC)


class Transport:
    def __init__(self, models=("reference-model",), healthy=True):
        self.models = models
        self.healthy = healthy
        self.keys = []

    async def list_models(self, base_url, api_key, timeout_seconds):
        self.keys.append(api_key)
        return self.models

    async def health(self, base_url, api_key, timeout_seconds):
        self.keys.append(api_key)
        return self.healthy

    async def create_chat_completion(self, base_url, request, api_key, timeout_seconds):
        raise AssertionError("configuration must not invoke inference")


def write_config(tmp_path, *, model="reference-model", credential=None):
    optional_model = "" if model is None else f"    model: {model}\n"
    optional_credential = "" if credential is None else f"    credential: {credential}\n"
    path = tmp_path / "models.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "schema_version: '1.0'\n"
        "selected: local_default\n"
        "profiles:\n"
        "  local_default:\n"
        "    type: local_openai\n"
        "    base_url: http://127.0.0.1:11434/v1\n"
        f"{optional_model}{optional_credential}",
        encoding="utf-8",
    )
    return path


def registry(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    subject = ModelQualificationRegistry(tmp_path / "models.sqlite")
    document = attestation()
    document["qualification"]["provider_id"] = "local_openai"
    document["qualification"]["adapter_version"] = "1.0"
    subject.register(document, registered_at=REGISTERED_AT, registered_by="release-controller")
    return subject


def resolve(configuration, transport, qualifications, resolver=None):
    return resolve_agent_model_sync(
        configuration,
        transport=transport,
        qualifications=qualifications,
        resolver=resolver or SecretResolver(),
        at=NOW,
    )


def test_explicit_qualified_local_model_resolves_without_inference(tmp_path) -> None:
    configuration = load_agent_model_config(write_config(tmp_path))
    transport = Transport()
    result = resolve(configuration, transport, registry(tmp_path))
    assert result.model == "reference-model"
    assert transport.keys == [None]
    assert configuration.profiles["local_default"].public_dict()["model"] == "reference-model"


def test_discovery_selects_only_one_qualified_model(tmp_path) -> None:
    configuration = load_agent_model_config(write_config(tmp_path, model=None))
    assert resolve(configuration, Transport(), registry(tmp_path)).model == "reference-model"
    with pytest.raises(AgentModelConfigError, match="explicitly"):
        resolve(configuration, Transport(("one", "two")), registry(tmp_path / "other"))


def test_unqualified_or_unavailable_model_fails_closed(tmp_path) -> None:
    configuration = load_agent_model_config(write_config(tmp_path, model="unknown-model"))
    with pytest.raises(AgentModelConfigError, match="lacks current qualification"):
        resolve(configuration, Transport(), registry(tmp_path))

    configuration = load_agent_model_config(write_config(tmp_path))
    with pytest.raises(AgentModelConfigError, match="unavailable"):
        resolve(configuration, Transport(healthy=False), registry(tmp_path / "unavailable"))


def test_credential_reference_is_redacted_and_scoped_to_transport(tmp_path) -> None:
    configuration = load_agent_model_config(
        write_config(tmp_path, credential="env:LOCAL_MODEL_KEY")
    )
    transport = Transport()
    resolve(
        configuration,
        transport,
        registry(tmp_path),
        SecretResolver(environment={"LOCAL_MODEL_KEY": "fixture-key"}),
    )
    assert transport.keys == ["fixture-key"]
    assert configuration.profiles["local_default"].public_dict()["credential"] == (
        "<redacted-reference>"
    )


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ("selected: local_default", "selected: missing"),
        ("http://127.0.0.1:11434/v1", "http://example.com:11434/v1"),
        ("type: local_openai", "type: arbitrary_remote"),
    ],
)
def test_invalid_selection_endpoint_and_type_are_rejected(tmp_path, original, replacement) -> None:
    path = write_config(tmp_path)
    path.write_text(path.read_text().replace(original, replacement), encoding="utf-8")
    with pytest.raises(AgentModelConfigError):
        load_agent_model_config(path)


def test_aliases_unknown_fields_and_literal_credentials_are_rejected(tmp_path) -> None:
    path = write_config(tmp_path)
    path.write_text(
        path.read_text()
        .replace(
            "profiles:\n  local_default:",
            "profiles:\n  local_default: &profile",
        )
        .replace("    type: local_openai", "    type: local_openai\n    extra: rejected"),
        encoding="utf-8",
    )
    with pytest.raises(AgentModelConfigError):
        load_agent_model_config(path)

    path = write_config(tmp_path, credential="literal-provider-key")
    with pytest.raises(ValueError, match="opaque reference"):
        load_agent_model_config(path)
