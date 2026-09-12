import asyncio
import io
import json
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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


class CloudTransport:
    def __init__(self) -> None:
        suite = load_benchmark_suite(CORPUS, expected_digest=ANCHOR.read_text().strip())
        self.outputs = [json.dumps(dict(case.expected_output)) for case in suite.cases]

    async def health(self, api_key: str) -> bool:
        return api_key == "fixture-value"

    async def create(self, request: Mapping[str, object], api_key: str) -> Mapping[str, Any]:
        assert request["store"] is False
        assert api_key == "fixture-value"
        output = self.outputs.pop(0)
        return {
            "id": f"resp_fixture_{len(self.outputs)}",
            "status": "completed",
            "output_text": output,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

    async def retrieve(self, response_id: str, api_key: str) -> Mapping[str, Any]:
        raise AssertionError("completed evaluation responses must not be retrieved")

    async def cancel_response(self, response_id: str, api_key: str) -> Mapping[str, Any]:
        raise AssertionError("completed evaluation responses must not be cancelled")


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


def test_explicit_openai_cloud_evaluation_uses_official_adapter(tmp_path: Path) -> None:
    output = tmp_path / "cloud-evaluation.json"
    args = arguments(output)
    args[1] = "https://api.openai.com/v1"
    args[-1] = "--authorize-cloud"
    args.extend(["--provider", "openai", "--credential-ref", "env:OPENAI_API_KEY"])
    stdout, stderr = io.StringIO(), io.StringIO()
    code = asyncio.run(
        run_local_model_cli(
            args,
            stdout=stdout,
            stderr=stderr,
            environment={"OPENAI_API_KEY": "fixture-value"},
            cloud_transport=CloudTransport(),
        )
    )
    assert code == ExitCode.SUCCESS
    assert stderr.getvalue() == ""
    manifest = json.loads(output.read_text())
    assert manifest["provider_id"] == "openai"
    assert manifest["model_id"] == "reference-model"
    assert set(manifest["report"]["category_results"].values()) == {"PASS"}
    assert "OPENAI_API_KEY" not in output.read_text()


def test_openai_cloud_evaluation_rejects_arbitrary_endpoint(tmp_path: Path) -> None:
    args = arguments(tmp_path / "rejected.json")
    args[1] = "https://example.com/v1"
    args[-1] = "--authorize-cloud"
    args.extend(["--provider", "openai", "--credential-ref", "env:OPENAI_API_KEY"])
    assert invoke(args, environment={"OPENAI_API_KEY": "fixture-value"})[0] == ExitCode.VALIDATION
