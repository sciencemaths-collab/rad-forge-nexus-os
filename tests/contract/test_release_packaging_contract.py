import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_alpha_3_versions_and_release_commands_are_aligned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    scripts = project["scripts"]
    assert project["version"] == "0.2.0a3"
    assert "pytest>=9.0.3,<10" in project["dependencies"]
    assert scripts["rad"] == "nexus_os.rad_cli:main"
    assert scripts["rad-config-migrate"] == "nexus_os.config_migration:main"
    assert '__version__ = "0.2.0a3"' in (ROOT / "src/nexus_os/__init__.py").read_text(
        encoding="utf-8"
    )
    typescript = (ROOT / "sdk/typescript/package.json").read_text(encoding="utf-8")
    assert '"version": "0.2.0-alpha.3"' in typescript


def test_container_is_pinned_non_root_and_installs_only_the_built_wheel() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "@sha256:" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "pip install --no-cache-dir /tmp/nexus_os-0.2.0a3-py3-none-any.whl" in dockerfile
    assert "!dist/nexus_os-0.2.0a3-py3-none-any.whl" in dockerignore
    assert 'ENTRYPOINT ["rad"]' in dockerfile


def test_quickstart_uses_real_release_channels_and_documents_container_boundary() -> None:
    quickstart = (ROOT / "docs/QUICKSTART_5_MINUTES.md").read_text(encoding="utf-8")
    assert "pipx install nexus-os==" not in quickstart
    assert "gh release download v0.2.0a3" in quickstart
    assert "gh attestation verify nexus_os-0.2.0a3-py3-none-any.whl" in quickstart
    assert "ghcr.io/sciencemaths-collab/rad-agent:v0.2.0a3" in quickstart
    assert "--network host" in quickstart
    assert "without a moving `latest` tag" in quickstart


def test_tag_release_requires_qualification_checksums_attestations_and_sbom() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    text = str(workflow)
    assert "scripts/release_evidence.py" in text
    assert "SHA256SUMS" in text
    assert "actions/attest-build-provenance@v3" in text
    assert "--sbom=true" in text
    assert "steps.image.outputs.subject" in text
    assert "candidate-${{ github.sha }}" in text
    assert "docker buildx imagetools create" in text
    assert text.index("actions/attest-build-provenance@v3") < text.index(
        "docker buildx imagetools create"
    )
    assert "gh release create" in text
    assert "--prerelease" in text
