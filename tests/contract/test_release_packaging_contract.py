import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_alpha_2_versions_and_release_commands_are_aligned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    scripts = project["scripts"]
    assert project["version"] == "0.2.0a2"
    assert scripts["rad"] == "nexus_os.rad_cli:main"
    assert scripts["rad-config-migrate"] == "nexus_os.config_migration:main"
    assert '__version__ = "0.2.0a2"' in (ROOT / "src/nexus_os/__init__.py").read_text(
        encoding="utf-8"
    )
    typescript = (ROOT / "sdk/typescript/package.json").read_text(encoding="utf-8")
    assert '"version": "0.2.0-alpha.2"' in typescript


def test_container_is_pinned_non_root_and_installs_only_the_built_wheel() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "@sha256:" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "pip install --no-cache-dir /tmp/rad-agent.whl" in dockerfile
    assert 'ENTRYPOINT ["rad"]' in dockerfile


def test_tag_release_requires_qualification_checksums_attestations_and_sbom() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    text = str(workflow)
    assert "scripts/release_evidence.py" in text
    assert "SHA256SUMS" in text
    assert "actions/attest-build-provenance@v3" in text
    assert "--sbom=true" in text
    assert "gh release create" in text
