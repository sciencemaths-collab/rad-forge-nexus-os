import json
import subprocess

import pytest

from scripts.release_evidence import GATES, ReleaseEvidenceError, run_release_gates


def _manifests(root) -> None:
    (root / "sdk/typescript").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='test'\n")
    (root / "uv.lock").write_text("version=1\n[[package]]\nname='alpha'\nversion='1.0'\n")
    (root / "sdk/typescript/package-lock.json").write_text('{"packages":{}}')


def test_generator_records_all_passes_but_not_release_approval(tmp_path) -> None:
    _manifests(tmp_path)

    def passing(command, root):
        return subprocess.CompletedProcess(command, 0, stdout=b"passed")

    report = run_release_gates(tmp_path, tmp_path / "out", runner=passing)
    assert report["automated_gates_pass"] is True
    assert report["release_candidate"] is False
    assert report["owner_approved"] is False
    assert len(report["gates"]) == len(GATES) + 1
    parsed = json.loads((tmp_path / "out/final-evidence-report.json").read_text())
    assert parsed["qualification_state"] == "AUTOMATED_GATES_PASS"
    assert (tmp_path / "out/sbom.cdx.json").is_file()
    assert (tmp_path / "out/build-provenance.json").is_file()


def test_generator_stops_at_first_failed_gate_and_writes_blocked_report(tmp_path) -> None:
    _manifests(tmp_path)
    calls = []

    def failing(command, root):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1 if len(calls) == 3 else 0, stdout=b"output")

    with pytest.raises(ReleaseEvidenceError, match="typecheck"):
        run_release_gates(tmp_path, tmp_path / "out", runner=failing)
    report = json.loads((tmp_path / "out/final-evidence-report.json").read_text())
    assert report["failed_gate"] == "typecheck"
    assert len(calls) == 3
