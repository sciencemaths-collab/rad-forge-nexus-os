import asyncio
import io
import json
from collections.abc import Mapping
from typing import Any

from nexus_os.cli import ExitCode, run_cli


class FakeClient:
    def __init__(self, status: int = 200, body: Mapping[str, Any] | list[Any] | None = None):
        self.status = status
        self.body = body if body is not None else []
        self.calls: list[tuple[str, str, Mapping[str, Any] | None, str | None]] = []

    async def request(self, method, path, *, body=None, idempotency_key=None):  # type: ignore[no-untyped-def]
        self.calls.append((method, path, body, idempotency_key))
        return self.status, self.body, {"X-Trace-Id": "a" * 32}


def invoke(arguments: list[str], client: FakeClient) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = asyncio.run(run_cli(arguments, client, stdout=stdout, stderr=stderr))
    return code, stdout.getvalue(), stderr.getvalue()


def test_runs_create_outputs_canonical_json_and_preserves_idempotency() -> None:
    body = {
        "run_id": "00000000-0000-4000-8000-000000000001",
        "project_id": "project-1",
        "state": "SPECIFYING",
    }
    client = FakeClient(202, body)
    code, output, error = invoke(
        ["runs", "create", "--project-id", "project-1", "--idempotency-key", "1234567890abcdef"],
        client,
    )
    assert code == ExitCode.SUCCESS
    assert json.loads(output) == body
    assert error == ""
    assert client.calls == [
        ("POST", "/v1/runs", {"project_id": "project-1"}, "1234567890abcdef")
    ]


def test_read_commands_map_to_expected_paths() -> None:
    identifier = "00000000-0000-4000-8000-000000000001"
    cases = (
        (["runs", "get", identifier], f"/v1/runs/{identifier}"),
        (["providers", "list"], "/v1/providers"),
        (["capabilities", "list"], "/v1/capabilities"),
    )
    for arguments, path in cases:
        client = FakeClient()
        code, _, _ = invoke(arguments, client)
        assert code == ExitCode.SUCCESS
        assert client.calls[0][:2] == ("GET", path)


def test_api_error_maps_to_stable_exit_class_without_traceback() -> None:
    client = FakeClient(403, {"code": "forbidden", "message": "Denied", "retryable": False})
    code, output, error = invoke(["providers", "list"], client)
    assert code == ExitCode.AUTHORIZATION
    assert output == ""
    assert json.loads(error)["code"] == "forbidden"
    assert "Traceback" not in error

