"""Verify the built RAD Agent wheel from an isolated installation."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


class CleanWheelAcceptanceError(RuntimeError):
    """A packaged-installation acceptance check failed."""


def _run(command: tuple[str, ...], cwd: Path) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(  # noqa: S603 - fixed, repository-controlled commands
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        diagnostic = (completed.stdout + completed.stderr)[-4000:]
        raise CleanWheelAcceptanceError(f"command failed safely: {command[0]}\n{diagnostic}")


def verify(root: Path) -> None:
    wheels = tuple(sorted((root / "dist").glob("nexus_os-*.whl")))
    if len(wheels) != 1:
        raise CleanWheelAcceptanceError("exactly one built RAD Agent wheel is required")
    with tempfile.TemporaryDirectory(prefix="rad-clean-wheel-") as directory:
        clean_root = Path(directory)
        environment = clean_root / "environment"
        _run(("uv", "venv", "--seed", str(environment)), clean_root)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        executable = environment / ("Scripts/rad.exe" if os.name == "nt" else "bin/rad")
        _run(("uv", "pip", "install", "--python", str(python), str(wheels[0])), clean_root)
        for arguments in (
            ("--help",),
            ("setup", "--help"),
            ("doctor", "--help"),
            ("serve", "--help"),
        ):
            _run((str(executable), *arguments), clean_root)
        _run(
            (
                str(python),
                "-c",
                "from nexus_os.agent_web_ui import APP_JS,INDEX_HTML;"
                "assert b'RAD Agent' in INDEX_HTML and b'verifyCompletion' in APP_JS",
            ),
            clean_root,
        )


def main() -> None:
    try:
        verify(Path(__file__).resolve().parents[1])
    except CleanWheelAcceptanceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("clean wheel acceptance passed")


if __name__ == "__main__":
    main()
