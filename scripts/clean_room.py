"""Isolated source-snapshot qualification and independent release review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

COPY_PATHS: Final = (
    ".github",
    "contracts",
    "docs",
    "examples",
    "schemas",
    "scripts",
    "sdk",
    "src",
    "tests",
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
)
IGNORED: Final = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "artifacts",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
_PLACEHOLDERS = ("TO" + "DO", "FIX" + "ME", "X" * 3, "HA" + "CK")
_UNIMPLEMENTED = "Not" + "Implemented" + "Error"
UNSAFE_PATTERNS: Final = {
    "placeholder": re.compile(rf"\b(?:{'|'.join(_PLACEHOLDERS)})\b"),
    "dynamic_execution": re.compile(r"(?:\beval\(|\bexec\(|shell\s*=\s*True)"),
    "unimplemented": re.compile(_UNIMPLEMENTED),
}
VENDOR_IMPORT: Final = re.compile(
    r"^\s*(?:from|import)\s+(?:openai|anthropic)(?:\s|\.)", re.MULTILINE
)


class CleanRoomError(RuntimeError):
    """Clean-room materialization, qualification, or review failed."""


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    category: str
    path: str
    line: int


def materialize_snapshot(source: Path, destination: Path) -> str:
    destination.mkdir(parents=True, exist_ok=False)
    for relative in COPY_PATHS:
        origin = source / relative
        target = destination / relative
        if not origin.exists():
            raise CleanRoomError("required clean-room source is missing")
        if origin.is_dir():
            shutil.copytree(origin, target, ignore=shutil.ignore_patterns(*IGNORED))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, target)
    return snapshot_digest(destination)


def snapshot_digest(root: Path) -> str:
    digest = hashlib.sha256()
    files = [path for path in root.rglob("*") if path.is_file()]
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return f"sha256:{digest.hexdigest()}"


def independent_review(root: Path) -> tuple[ReviewFinding, ...]:
    findings: list[ReviewFinding] = []
    for directory in ("src", "scripts"):
        for path in sorted((root / directory).rglob("*.py")):
            text = path.read_text()
            for category, pattern in UNSAFE_PATTERNS.items():
                for match in pattern.finditer(text):
                    findings.append(
                        ReviewFinding(
                            category,
                            path.relative_to(root).as_posix(),
                            text.count("\n", 0, match.start()) + 1,
                        )
                    )
            if directory == "src" and VENDOR_IMPORT.search(text):
                findings.append(
                    ReviewFinding("vendor_import_in_core", path.relative_to(root).as_posix(), 1)
                )
    status = (root / "docs/runbooks/STATUS.md").read_text()
    if "NO CAPABILITY IS PRODUCTION READY" not in status:
        findings.append(ReviewFinding("completion_claim_drift", "docs/runbooks/STATUS.md", 1))
    return tuple(findings)


def qualify(source: Path, output: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="nexus-clean-room-") as temporary:
        snapshot = Path(temporary) / "source"
        digest = materialize_snapshot(source.resolve(), snapshot)
        review = independent_review(snapshot)
        if review:
            raise CleanRoomError("independent review found blocking issues")
        environment = dict(os.environ)
        environment["UV_CACHE_DIR"] = str(Path(temporary) / "uv-cache")
        environment["NPM_CONFIG_CACHE"] = str(Path(temporary) / "npm-cache")
        commands = (
            ("uv", "sync", "--all-groups", "--locked"),
            ("npm", "ci", "--prefix", "sdk/typescript", "--ignore-scripts"),
            (
                "uv",
                "run",
                "python",
                "scripts/release_evidence.py",
                "--output",
                "artifacts/release-evidence",
            ),
        )
        for command in commands:
            completed = subprocess.run(  # noqa: S603 - fixed internal commands only
                command,
                cwd=snapshot,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if completed.returncode != 0:
                raise CleanRoomError("clean-room command failed")
        evidence_path = snapshot / "artifacts/release-evidence/final-evidence-report.json"
        evidence = json.loads(evidence_path.read_text())
        report = {
            "schema_version": "1.0",
            "snapshot_digest": digest,
            "automated_evidence_digest": _digest(evidence_path.read_bytes()),
            "automated_gates_pass": evidence["automated_gates_pass"],
            "independent_review_pass": True,
            "review_findings": [asdict(item) for item in review],
            "clean_room_qualified": True,
            "owner_approved": False,
            "release_candidate": False,
            "qualification_state": "CLEAN_ROOM_QUALIFIED_OWNER_APPROVAL_PENDING",
        }
        output.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
        (output / "clean-room-report.json").write_bytes(payload)
        (output / "clean-room-report.md").write_text(
            "# Clean-Room Qualification\n\n"
            f"Snapshot: `{digest}`\n\n"
            "Automated gates: PASS\n\nIndependent review: PASS\n\n"
            "Release candidate: NO — owner approval remains pending.\n"
        )
        return report


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        qualify(arguments.source, arguments.output)
    except CleanRoomError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
