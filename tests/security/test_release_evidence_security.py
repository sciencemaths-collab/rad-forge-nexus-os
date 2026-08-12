import subprocess

import pytest

from scripts.release_evidence import ReleaseEvidenceError, run_release_gates, scan_secrets


def _manifests(root) -> None:
    (root / "sdk/typescript").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='test'\n")
    (root / "uv.lock").write_text("version=1\n")
    (root / "sdk/typescript/package-lock.json").write_text('{"packages":{}}')


def test_secret_scan_detects_key_material_but_ignores_build_dirs(tmp_path) -> None:
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    (tmp_path / "source.txt").write_text(marker)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules/ignored.txt").write_text(marker)
    assert scan_secrets(tmp_path) == ("source.txt",)


def test_secret_findings_fail_release_without_echoing_secret(tmp_path) -> None:
    _manifests(tmp_path)
    (tmp_path / "leak.txt").write_text("sk-" + "A" * 24)

    def passing(command, root):
        return subprocess.CompletedProcess(command, 0, stdout=b"passed")

    with pytest.raises(ReleaseEvidenceError, match="secret_scan") as raised:
        run_release_gates(tmp_path, tmp_path / "out", runner=passing)
    assert "sk-" not in str(raised.value)
