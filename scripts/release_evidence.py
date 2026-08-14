"""Run fail-fast release gates and generate digest-bound evidence reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

REPORT_VERSION: Final = "1.0"
SECRET_PATTERNS: Final = (
    re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"sk-[A-Za-z0-9]{20,}"),
)
IGNORED_PARTS: Final = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    "tmp",
    "artifacts",
    "evidence",
    "upload",
    "__pycache__",
}


class ReleaseEvidenceError(RuntimeError):
    """A required release-evidence gate failed."""


@dataclass(frozen=True, slots=True)
class Gate:
    gate_id: str
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: str
    command: tuple[str, ...]
    outcome: str
    return_code: int
    output_digest: str


GATES: Final = (
    Gate("format", ("uv", "run", "ruff", "format", "--check", ".")),
    Gate("lint", ("uv", "run", "ruff", "check", ".")),
    Gate("typecheck", ("uv", "run", "mypy", "src", "scripts")),
    Gate("schemas", ("uv", "run", "python", "scripts/validate_contracts.py")),
    Gate(
        "python_dependency_audit",
        (
            "uv",
            "run",
            "pip-audit",
            "--progress-spinner=off",
            "--cache-dir",
            "artifacts/pip-audit-cache",
        ),
    ),
    Gate(
        "typescript_dependency_audit",
        ("npm", "audit", "--prefix", "sdk/typescript", "--audit-level=moderate"),
    ),
    Gate("unit", ("uv", "run", "pytest", "-q", "tests/unit")),
    Gate("contract", ("uv", "run", "pytest", "-q", "tests/contract")),
    Gate("integration", ("uv", "run", "pytest", "-q", "tests/integration")),
    Gate("security", ("uv", "run", "pytest", "-q", "tests/security")),
    Gate("build", ("uv", "build", "--offline")),
    Gate("clean_wheel", ("uv", "run", "python", "scripts/clean_wheel_acceptance.py")),
    Gate(
        "browser_acceptance",
        (
            "uv",
            "run",
            "pytest",
            "-q",
            "tests/browser",
            "--browser",
            "chromium",
            "--browser",
            "firefox",
            "--tracing",
            "retain-on-failure",
            "--screenshot",
            "only-on-failure",
            "--video",
            "retain-on-failure",
            "--output",
            "artifacts/browser-acceptance",
        ),
    ),
    Gate(
        "provider_conformance",
        ("uv", "run", "pytest", "-q", "tests/integration/test_provider_conformance_registry.py"),
    ),
    Gate(
        "rw_100k",
        ("uv", "run", "pytest", "-q", "tests/integration/test_reference_workflow_e2e.py"),
    ),
    Gate("typescript", ("npm", "test", "--prefix", "sdk/typescript")),
    Gate(
        "qualified_browser",
        (
            "uv",
            "run",
            "pytest",
            "-q",
            "tests/acceptance/test_packaged_qualified_browser.py",
            "--browser",
            "chromium",
            "--browser",
            "firefox",
            "--tracing",
            "retain-on-failure",
            "--screenshot",
            "only-on-failure",
            "--output",
            "artifacts/qualified-browser",
        ),
    ),
)

type Runner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[bytes]]


def run_release_gates(
    root: Path,
    output: Path,
    *,
    runner: Runner | None = None,
) -> dict[str, object]:
    """Run every automated gate, stop on failure, and write an honest release bundle."""
    repository = root.resolve()
    destination = output.resolve()
    execute = runner or _run
    results: list[GateResult] = []
    failure: str | None = None
    for gate in GATES:
        completed = execute(gate.command, repository)
        result = GateResult(
            gate_id=gate.gate_id,
            command=gate.command,
            outcome="PASS" if completed.returncode == 0 else "FAIL",
            return_code=completed.returncode,
            output_digest=_digest(completed.stdout),
        )
        results.append(result)
        if completed.returncode != 0:
            failure = gate.gate_id
            diagnostic = completed.stdout.decode("utf-8", errors="replace")
            print(diagnostic[-4000:], file=sys.stderr)
            break
    if failure is None:
        findings = scan_secrets(repository)
        secret_result = GateResult(
            "secret_scan",
            ("internal:secret_scan",),
            "PASS" if not findings else "FAIL",
            0 if not findings else 1,
            _digest("\n".join(findings).encode()),
        )
        results.append(secret_result)
        if findings:
            failure = "secret_scan"
    report = _report(repository, results, failure)
    _write_bundle(destination, report, repository)
    if failure is not None:
        raise ReleaseEvidenceError(f"release gate failed: {failure}")
    return report


def scan_secrets(root: Path) -> tuple[str, ...]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        ignored = any(part in IGNORED_PARTS for part in path.relative_to(root).parts)
        if not path.is_file() or ignored:
            continue
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ReleaseEvidenceError("secret scan could not read repository content") from exc
        if any(pattern.search(payload) for pattern in SECRET_PATTERNS):
            findings.append(path.relative_to(root).as_posix())
    return tuple(findings)


def _report(root: Path, results: list[GateResult], failure: str | None) -> dict[str, object]:
    inputs = {
        name: _file_digest(root / name)
        for name in ("pyproject.toml", "uv.lock", "sdk/typescript/package-lock.json")
    }
    automated_pass = failure is None and len(results) == len(GATES) + 1
    return {
        "schema_version": REPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "ci": os.environ.get("CI") == "true",
            "commit": os.environ.get("GITHUB_SHA"),
        },
        "input_digests": inputs,
        "gates": [asdict(item) for item in results],
        "automated_gates_pass": automated_pass,
        "failed_gate": failure,
        "clean_room_qualified": False,
        "owner_approved": False,
        "release_candidate": False,
        "qualification_state": "AUTOMATED_GATES_PASS" if automated_pass else "BLOCKED",
    }


def _write_bundle(output: Path, report: dict[str, object], root: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    report_bytes = _canonical(report)
    (output / "final-evidence-report.json").write_bytes(report_bytes)
    (output / "sbom.cdx.json").write_bytes(_canonical(_sbom(root)))
    (output / "build-provenance.json").write_bytes(
        _canonical(
            {
                "schema_version": "1.0",
                "report_digest": _digest(report_bytes),
                "commit": os.environ.get("GITHUB_SHA"),
                "workflow": os.environ.get("GITHUB_WORKFLOW"),
                "run_id": os.environ.get("GITHUB_RUN_ID"),
                "builder": "scripts/release_evidence.py",
            }
        )
    )
    report_digest = _digest(report_bytes)
    gates = report["gates"]
    if not isinstance(gates, list):
        raise ReleaseEvidenceError("release report gates are invalid")
    lines = ["# Final Evidence Report", "", f"Digest: `{report_digest}`", ""]
    for gate in gates:
        if not isinstance(gate, dict):
            raise ReleaseEvidenceError("release report gate is invalid")
        lines.append(f"- {gate['gate_id']}: {gate['outcome']} (`{gate['output_digest']}`)")
    lines.extend(
        ["", "Release candidate: NO — clean-room qualification and owner approval pending.", ""]
    )
    (output / "final-evidence-report.md").write_text("\n".join(lines))
    (output / "KNOWN_LIMITATIONS.md").write_text(
        "# Known Limitations\n\n"
        "- No component is production-qualified.\n"
        "- Live providers, production HTTP/MCP hosting, deployment, and package publication "
        "are unverified.\n"
        "- RW-100K is runtime-only; virtual-grid and browser performance are unimplemented.\n"
        "- Clean-room qualification and independent review remain Component AG.\n"
    )
    (output / "RELEASE_CANDIDATE_CHECKLIST.md").write_text(
        "# Release Candidate Checklist\n\n"
        "- [x] Automated gates recorded\n"
        "- [x] Evidence report digest generated\n"
        "- [ ] Clean-room qualification completed\n"
        "- [ ] Independent review completed\n"
        "- [ ] Owner approval bound to final artifact digest\n"
        "- [ ] Production release authorized\n"
    )


def _run(command: Sequence[str], root: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 - command is selected only from frozen GATES
        command,
        cwd=root,
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _sbom(root: Path) -> dict[str, object]:
    try:
        python_lock = tomllib.loads((root / "uv.lock").read_text())
        npm_lock = json.loads((root / "sdk/typescript/package-lock.json").read_text())
    except (OSError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseEvidenceError("dependency lockfile is unavailable or invalid") from exc
    components: list[dict[str, str]] = []
    for package in python_lock.get("package", []):
        if isinstance(package, dict) and isinstance(package.get("name"), str):
            components.append(
                {
                    "type": "library",
                    "name": package["name"],
                    "version": str(package.get("version", "")),
                }
            )
    packages = npm_lock.get("packages", {})
    if isinstance(packages, dict):
        for path, package in packages.items():
            if path and isinstance(package, dict) and isinstance(package.get("version"), str):
                components.append(
                    {
                        "type": "library",
                        "name": path.removeprefix("node_modules/"),
                        "version": package["version"],
                    }
                )
    components.sort(key=lambda item: (item["name"], item["version"]))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "components": components,
    }


def _file_digest(path: Path) -> str:
    try:
        return _digest(path.read_bytes())
    except OSError as exc:
        raise ReleaseEvidenceError("release input manifest is unavailable") from exc


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        run_release_gates(arguments.root, arguments.output)
    except ReleaseEvidenceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
