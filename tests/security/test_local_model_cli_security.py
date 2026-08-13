import asyncio
import io
import json
from pathlib import Path

import pytest

from nexus_os.cli import ExitCode
from nexus_os.local_model_cli import run_local_model_cli
from tests.unit.test_local_model_cli import arguments, transport


def invoke(args: list[str], *, factory=None):  # type: ignore[no-untyped-def]
    stdout, stderr = io.StringIO(), io.StringIO()
    code = asyncio.run(
        run_local_model_cli(
            args,
            stdout=stdout,
            stderr=stderr,
            transport_factory=factory or (lambda sandbox: transport()),
        )
    )
    return code, stdout.getvalue(), stderr.getvalue()


def test_missing_authorization_remote_endpoint_and_non_utc_time_are_rejected(
    tmp_path: Path,
) -> None:
    base = arguments(tmp_path / "manifest.json")
    cases = (
        [item for item in base if item != "--authorize-loopback"],
        [
            "http://example.com:11434/v1" if item == "http://127.0.0.1:11434/v1" else item
            for item in base
        ],
        ["2026-08-13T16:00:00+01:00" if item == "2026-08-13T16:00:00Z" else item for item in base],
    )
    for case in cases:
        code, output, error = invoke(case)
        assert code == ExitCode.VALIDATION
        assert output == ""
        assert json.loads(error)["code"] == "local_evaluation_validation"


def test_existing_file_and_symlink_are_never_overwritten(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text("preserve")
    assert invoke(arguments(existing))[0] == ExitCode.VALIDATION
    assert existing.read_text() == "preserve"

    target = tmp_path / "target.json"
    target.write_text("preserve-target")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert invoke(arguments(link))[0] == ExitCode.VALIDATION
    assert target.read_text() == "preserve-target"


def test_transport_exception_is_sanitized_and_writes_no_partial_output(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"

    class Broken:
        async def run(self, task):  # type: ignore[no-untyped-def]
            raise RuntimeError("SENSITIVE_PROVIDER_BODY")

    code, stdout, stderr = invoke(arguments(output), factory=lambda sandbox: Broken())
    assert code == ExitCode.SUCCESS
    assert "SENSITIVE_PROVIDER_BODY" not in stdout + stderr + output.read_text()
    manifest = json.loads(output.read_text())
    assert set(manifest["report"]["category_results"].values()) == {"FAIL"}


def test_literal_or_unsupported_credential_reference_is_rejected(tmp_path: Path) -> None:
    for reference in ("literal-value", "vault:path/to/key"):
        args = [
            *arguments(tmp_path / f"{reference.split(':')[0]}.json"),
            "--credential-ref",
            reference,
        ]
        assert invoke(args)[0] == ExitCode.VALIDATION
