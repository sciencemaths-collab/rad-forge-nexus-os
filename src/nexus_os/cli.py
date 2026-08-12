"""Thin machine-readable CLI over a control API client port."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Mapping, Sequence
from enum import IntEnum
from typing import Any, NoReturn, Protocol, TextIO


class ExitCode(IntEnum):
    SUCCESS = 0
    VALIDATION = 2
    AUTHORIZATION = 3
    EXECUTION = 4
    INTEGRITY = 5
    INTERNAL = 70


class ControlClient(Protocol):
    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[int, Mapping[str, Any] | list[Any], Mapping[str, str]]: ...


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError("invalid command arguments")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="nexus", add_help=True)
    root = parser.add_subparsers(dest="group", required=True)

    runs = root.add_parser("runs")
    run_commands = runs.add_subparsers(dest="command", required=True)
    create = run_commands.add_parser("create")
    create.add_argument("--project-id", required=True)
    create.add_argument("--idempotency-key", required=True)
    get = run_commands.add_parser("get")
    get.add_argument("run_id")
    for command in ("cancel", "resume"):
        item = run_commands.add_parser(command)
        item.add_argument("run_id")
        item.add_argument("--idempotency-key", required=True)

    evidence = root.add_parser("evidence")
    evidence_commands = evidence.add_subparsers(dest="command", required=True)
    verify = evidence_commands.add_parser("verify")
    verify.add_argument("run_id")

    for group in ("providers", "capabilities"):
        item = root.add_parser(group)
        commands = item.add_subparsers(dest="command", required=True)
        commands.add_parser("list")
    return parser


async def run_cli(
    arguments: Sequence[str],
    client: ControlClient,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        values = _parser().parse_args(list(arguments))
        method, path, body, key = _command(values)
    except (ValueError, SystemExit):
        _write(stderr, {"code": "cli_validation", "message": "Invalid command arguments"})
        return ExitCode.VALIDATION
    try:
        status, response, headers = await client.request(
            method, path, body=body, idempotency_key=key
        )
        del headers
    except Exception:
        _write(stderr, {"code": "internal_error", "message": "Control client failed"})
        return ExitCode.INTERNAL
    if not isinstance(status, int) or not isinstance(response, (Mapping, list)):
        _write(stderr, {"code": "internal_error", "message": "Invalid control response"})
        return ExitCode.INTERNAL
    if status >= 400:
        safe = _safe_error(response)
        _write(stderr, safe)
        if status in {401, 403} or safe.get("code") in {"approval_required", "forbidden"}:
            return ExitCode.AUTHORIZATION
        if status in {400, 404, 409, 422}:
            return ExitCode.VALIDATION
        return ExitCode.EXECUTION
    if values.group == "evidence" and isinstance(response, Mapping):
        if response.get("valid") is not True:
            _write(stderr, response)
            return ExitCode.INTEGRITY
    _write(stdout, response)
    return ExitCode.SUCCESS


def _command(
    values: argparse.Namespace,
) -> tuple[str, str, Mapping[str, Any] | None, str | None]:
    if values.group == "runs":
        if values.command == "create":
            _bounded(values.project_id, "project_id")
            _key(values.idempotency_key)
            return "POST", "/v1/runs", {"project_id": values.project_id}, values.idempotency_key
        run_id = _uuid(values.run_id)
        if values.command == "get":
            return "GET", f"/v1/runs/{run_id}", None, None
        _key(values.idempotency_key)
        return "POST", f"/v1/runs/{run_id}/{values.command}", None, values.idempotency_key
    if values.group == "evidence":
        run_id = _uuid(values.run_id)
        return "GET", f"/v1/runs/{run_id}/evidence", None, None
    if values.group in {"providers", "capabilities"}:
        return "GET", f"/v1/{values.group}", None, None
    raise ValueError("unsupported command")


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("identifier is invalid")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ValueError("identifier is invalid") from exc


def _bounded(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError(f"{name} is invalid")
    return value


def _key(value: object) -> str:
    if not isinstance(value, str) or not 16 <= len(value) <= 128 or not value.isascii():
        raise ValueError("idempotency key is invalid")
    return value


def _safe_error(value: Mapping[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(value, Mapping):
        code = value.get("code")
        message = value.get("message")
        if isinstance(code, str) and isinstance(message, str):
            return {"code": code[:128], "message": message[:2000]}
    return {"code": "api_error", "message": "Control request failed"}


def _write(stream: TextIO, value: object) -> None:
    stream.write(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    stream.write("\n")


def main() -> int:
    """Installed entry point; client wiring is intentionally deferred to the SDK component."""
    _write(
        sys.stderr,
        {"code": "client_not_configured", "message": "Configure the NEXUS control client"},
    )
    return ExitCode.INTERNAL


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(asyncio.run(asyncio.to_thread(main)))
