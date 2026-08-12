from __future__ import annotations

from pathlib import Path

import pytest

from nexus_os.config import ConfigError, load_project_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "project.mock.yaml"


def test_process_environment_is_not_read_implicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS__POLICY__MAX_ATTEMPTS", "20")

    loaded = load_project_config(EXAMPLE)

    assert loaded.data["policy"]["max_attempts"] == 3


def test_literal_credential_overlay_is_rejected(tmp_path: Path) -> None:
    config = EXAMPLE.read_text(encoding="utf-8").replace(
        "adapter: mock\n    model:",
        "adapter: mock\n    credential: env:MOCK_KEY\n    model:",
        1,
    )
    path = tmp_path / "project.yaml"
    path.write_text(config, encoding="utf-8")

    with pytest.raises(ConfigError, match="literal secret"):
        load_project_config(
            path,
            environ={"NEXUS__PROVIDERS__PLANNER__CREDENTIAL": "plaintext-canary"},
        )
