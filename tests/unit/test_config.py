from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexus_os.config import ConfigError, load_project_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "project.mock.yaml"


def test_loads_valid_project_and_applies_explicit_defaults() -> None:
    loaded = load_project_config(EXAMPLE)

    assert loaded.data["workspace"]["read_only"] is False
    assert loaded.data["providers"]["planner"]["fallback"] == []
    assert loaded.digest.startswith("sha256:")
    assert len(loaded.digest) == 71


def test_canonical_digest_is_stable_across_yaml_and_json(tmp_path: Path) -> None:
    yaml_loaded = load_project_config(EXAMPLE)
    json_path = tmp_path / "project.json"
    json_path.write_text(yaml_loaded.canonical_json, encoding="utf-8")

    json_loaded = load_project_config(json_path)

    assert json_loaded.digest == yaml_loaded.digest
    assert json_loaded.canonical_json == yaml_loaded.canonical_json


def test_returned_data_cannot_mutate_canonical_state() -> None:
    loaded = load_project_config(EXAMPLE)
    exposed = loaded.data
    exposed["policy"]["max_attempts"] = 20

    assert loaded.data["policy"]["max_attempts"] == 3


def test_environment_overlay_is_typed_and_deterministic() -> None:
    loaded = load_project_config(EXAMPLE, environ={"NEXUS__POLICY__MAX_ATTEMPTS": "7"})

    assert loaded.data["policy"]["max_attempts"] == 7


@pytest.mark.parametrize(
    "environment",
    [
        {"NEXUS__POLICY__UNKNOWN": "1"},
        {"NEXUS__UNKNOWN": "1"},
    ],
)
def test_unknown_environment_overlay_is_rejected(environment: dict[str, str]) -> None:
    with pytest.raises(ConfigError, match="unknown"):
        load_project_config(EXAMPLE, environ=environment)


def test_redacted_manifest_never_contains_secret_reference(tmp_path: Path) -> None:
    config = (
        EXAMPLE.read_text(encoding="utf-8")
        .replace("secrets: {}", "secrets:\n  provider_key: env:OPENAI_API_KEY")
        .replace(
            "adapter: mock\n    model:",
            "adapter: mock\n    credential: secret:providers/mock\n    model:",
            1,
        )
    )
    path = tmp_path / "project.yaml"
    path.write_text(config, encoding="utf-8")

    manifest = load_project_config(path).redacted_manifest()
    serialized = json.dumps(manifest)

    assert "OPENAI_API_KEY" not in serialized
    assert "secret:providers/mock" not in serialized
    assert serialized.count("<redacted-reference>") == 2


def test_rejects_unknown_key_before_return(tmp_path: Path) -> None:
    path = tmp_path / "project.yaml"
    path.write_text(EXAMPLE.read_text(encoding="utf-8") + "unknown: true\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Additional properties"):
        load_project_config(path)


def test_rejects_literal_secret() -> None:
    with pytest.raises(ConfigError, match="credential"):
        load_project_config(ROOT / "tests" / "fixtures" / "project.invalid-secret.yaml")


def test_rejects_malformed_and_unsupported_documents(tmp_path: Path) -> None:
    malformed = tmp_path / "project.yaml"
    malformed.write_text("[not: valid", encoding="utf-8")
    unsupported = tmp_path / "project.toml"
    unsupported.write_text("schema_version = '1.0'", encoding="utf-8")

    with pytest.raises(ConfigError, match="malformed"):
        load_project_config(malformed)
    with pytest.raises(ConfigError, match="must use"):
        load_project_config(unsupported)


def test_rejects_oversized_input_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "project.yaml"
    path.write_text("x" * 11, encoding="utf-8")

    with pytest.raises(ConfigError, match="exceeds"):
        load_project_config(path, max_bytes=10)


def test_rejects_yaml_aliases_and_anchors(tmp_path: Path) -> None:
    path = tmp_path / "project.yaml"
    path.write_text("shared: &shared value\ncopy: *shared\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="anchors"):
        load_project_config(path)
