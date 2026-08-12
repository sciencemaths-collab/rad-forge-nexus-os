import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
SDK = ROOT / "sdk" / "typescript"


def test_typescript_sdk_is_dependency_free_and_strict() -> None:
    package = json.loads((SDK / "package.json").read_text())
    config = json.loads((SDK / "tsconfig.json").read_text())["compilerOptions"]

    assert "dependencies" not in package
    assert config["strict"] is True
    assert config["exactOptionalPropertyTypes"] is True
    assert config["noUncheckedIndexedAccess"] is True


def test_typescript_sdk_covers_frozen_control_surface() -> None:
    source = (SDK / "src" / "index.ts").read_text()

    for method in (
        "createRun",
        "getRun",
        "cancelRun",
        "resumeRun",
        "listProviders",
        "listCapabilities",
        "listEvidence",
    ):
        assert f"async {method}(" in source
    for path in ("/v1/runs", "/v1/providers", "/v1/capabilities", "/evidence"):
        assert path in source


def test_typescript_sdk_does_not_discover_credentials_or_endpoints() -> None:
    source = (SDK / "src" / "index.ts").read_text()

    assert "process.env" not in source
    assert "Authorization" not in source
    assert "http://" not in source
    assert "https://" not in source
