import asyncio
import io
import json
import stat
from pathlib import Path

from nexus_os.cli import ExitCode
from nexus_os.local_model_cli import run_local_model_cli
from nexus_os.model_evaluation import load_benchmark_suite
from tests.unit.test_model_evaluation import ScriptedTransport
from tests.unit.test_model_evaluation_corpus import ANCHOR, CORPUS


def arguments(output: Path) -> list[str]:
    return [
        "--base-url",
        "http://127.0.0.1:11434/v1",
        "--model",
        "reference-model",
        "--corpus",
        str(CORPUS),
        "--corpus-digest",
        ANCHOR.read_text().strip(),
        "--output",
        str(output),
        "--run-id",
        "40000000-0000-4000-8000-000000000001",
        "--trace-id",
        "4" * 32,
        "--evaluated-at",
        "2026-08-13T16:00:00Z",
        "--authorize-loopback",
    ]


def transport():
    suite = load_benchmark_suite(CORPUS, expected_digest=ANCHOR.read_text().strip())
    outputs = [json.dumps(dict(case.expected_output)) for case in suite.cases]
    return ScriptedTransport(outputs)


def invoke(args: list[str], *, environment=None):  # type: ignore[no-untyped-def]
    stdout, stderr = io.StringIO(), io.StringIO()
    code = asyncio.run(
        run_local_model_cli(
            args,
            stdout=stdout,
            stderr=stderr,
            environment=environment,
            transport_factory=lambda sandbox: transport(),
        )
    )
    return code, stdout.getvalue(), stderr.getvalue()


def test_command_writes_new_private_manifest_and_reports_not_qualified(tmp_path: Path) -> None:
    output = tmp_path / "evaluation.json"
    code, stdout, stderr = invoke(arguments(output))
    assert code == ExitCode.SUCCESS
    assert stderr == ""
    summary = json.loads(stdout)
    manifest = json.loads(output.read_text())
    assert summary["qualification_state"] == "NOT_QUALIFIED"
    assert manifest["qualification_state"] == "NOT_QUALIFIED"
    assert manifest["model_id"] == "reference-model"
    assert manifest["report"]["corpus_digest"] == ANCHOR.read_text().strip()
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert manifest["manifest_digest"] == summary["manifest_digest"]


def test_credential_reference_is_resolved_but_never_serialized(tmp_path: Path) -> None:
    output = tmp_path / "evaluation.json"
    args = [*arguments(output), "--credential-ref", "env:LOCAL_MODEL_KEY"]
    code, _, _ = invoke(args, environment={"LOCAL_MODEL_KEY": "fixture-value"})
    assert code == ExitCode.SUCCESS
    serialized = output.read_text()
    assert "LOCAL_MODEL_KEY" not in serialized
    assert "fixture-value" not in serialized
    assert "credential" not in serialized


def test_same_inputs_produce_same_manifest_digest(tmp_path: Path) -> None:
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    assert invoke(arguments(first))[0] == ExitCode.SUCCESS
    assert invoke(arguments(second))[0] == ExitCode.SUCCESS
    assert (
        json.loads(first.read_text())["manifest_digest"]
        == json.loads(second.read_text())["manifest_digest"]
    )
