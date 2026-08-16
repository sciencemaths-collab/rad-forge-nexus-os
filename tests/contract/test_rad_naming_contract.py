import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT_PUBLIC_FILES = (
    ROOT / "README.md",
    ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml",
    ROOT / "docs/architecture/ARCHITECTURE.md",
    ROOT / "docs/specifications/ACCEPTANCE_SPEC.md",
    ROOT / "docs/specifications/AGENT_APPLICATION_API.md",
    ROOT / "docs/specifications/AGENT_MODEL_CONFIGURATION.md",
    ROOT / "docs/specifications/AGENT_REASONING_CONTROLLER.md",
    ROOT / "docs/specifications/AGENT_RUNTIME_HANDOFF.md",
    ROOT / "docs/specifications/AGENT_SESSION_STORE.md",
    ROOT / "docs/specifications/LOCAL_AGENT_HTTP_SERVER.md",
    ROOT / "docs/specifications/NEXUS_AGENT_SPEC.md",
    ROOT / "docs/specifications/PRODUCT_SPEC.md",
)
LEGACY_PRODUCT_LABELS = ("NEXUS Agent", "NEXUS OS", "NEXUS API", "NEXUS SDK")


def test_current_public_surfaces_use_rad_agent_branding() -> None:
    for path in CURRENT_PUBLIC_FILES:
        text = path.read_text(encoding="utf-8")
        assert "RAD Agent" in text, path
        for legacy in LEGACY_PRODUCT_LABELS:
            assert legacy not in text, f"{path}: {legacy}"


def test_primary_commands_and_deprecated_aliases_remain_installed() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = project["project"]["scripts"]

    assert scripts["rad"] == "nexus_os.rad_cli:main"
    assert scripts["rad-agent-serve"] == "nexus_os.agent_server_cli:main"
    assert scripts["rad-model-eval"] == "nexus_os.local_model_cli:main"
    assert scripts["nexus-agent-serve"] == scripts["rad-agent-serve"]
    assert scripts["nexus-model-eval"] == scripts["rad-model-eval"]
