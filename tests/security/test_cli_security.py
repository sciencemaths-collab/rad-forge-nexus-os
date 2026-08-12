import asyncio
import io
import json

from nexus_os.cli import ExitCode, run_cli


class Client:
    async def request(self, method, path, *, body=None, idempotency_key=None):  # type: ignore[no-untyped-def]
        return 200, [], {}


def invoke(arguments: list[str]) -> tuple[int, str]:
    stderr = io.StringIO()
    code = asyncio.run(run_cli(arguments, Client(), stdout=io.StringIO(), stderr=stderr))
    return code, stderr.getvalue()


def test_invalid_uuid_key_and_oversized_identifier_are_rejected_before_client() -> None:
    cases = (
        ["runs", "get", "not-a-uuid"],
        ["runs", "create", "--project-id", "p", "--idempotency-key", "short"],
        ["runs", "create", "--project-id", "x" * 257, "--idempotency-key", "1234567890abcdef"],
    )
    for arguments in cases:
        code, error = invoke(arguments)
        assert code == ExitCode.VALIDATION
        assert json.loads(error)["code"] == "cli_validation"


def test_evidence_invalid_returns_integrity_exit_code() -> None:
    class InvalidEvidence(Client):
        async def request(self, method, path, *, body=None, idempotency_key=None):  # type: ignore[no-untyped-def]
            return 200, {"valid": False, "record_count": 2, "errors": ["hash mismatch"]}, {}

    stderr = io.StringIO()
    code = asyncio.run(
        run_cli(
            ["evidence", "verify", "00000000-0000-4000-8000-000000000001"],
            InvalidEvidence(),
            stdout=io.StringIO(),
            stderr=stderr,
        )
    )
    assert code == ExitCode.INTEGRITY


def test_client_exception_is_sanitized() -> None:
    class Broken(Client):
        async def request(self, method, path, *, body=None, idempotency_key=None):  # type: ignore[no-untyped-def]
            raise RuntimeError("SECRET_CANARY")

    stderr = io.StringIO()
    code = asyncio.run(
        run_cli(["providers", "list"], Broken(), stdout=io.StringIO(), stderr=stderr)
    )
    assert code == ExitCode.INTERNAL
    assert "SECRET_CANARY" not in stderr.getvalue()
