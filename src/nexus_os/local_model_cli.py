"""Operator CLI for controlled evaluation of one explicit loopback reasoning model."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn, TextIO
from urllib.parse import urlsplit
from uuid import UUID

from nexus_os.cli import ExitCode
from nexus_os.domain import RunId, TraceId
from nexus_os.local_openai_adapter import LocalOpenAIAdapter, LocalOpenAITransport
from nexus_os.loopback_http_transport import LoopbackHTTPTransport
from nexus_os.model_evaluation import ModelEvaluationRunner, load_benchmark_suite
from nexus_os.sandbox import WorkspaceSandbox
from nexus_os.secrets import SecretReference, SecretResolver

_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_LOOPBACK = {"localhost": "127.0.0.1", "127.0.0.1": "127.0.0.1", "::1": "::1"}
TransportFactory = Callable[[WorkspaceSandbox], LocalOpenAITransport]


class LocalModelCLIError(ValueError):
    """Safe operator-input or output-persistence failure."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise LocalModelCLIError("invalid command arguments")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="rad-model-eval")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--corpus-digest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--evaluated-at", required=True)
    parser.add_argument("--credential-ref")
    parser.add_argument("--authorize-loopback", action="store_true")
    return parser


async def run_local_model_cli(
    arguments: Sequence[str],
    *,
    stdout: TextIO,
    stderr: TextIO,
    environment: Mapping[str, str] | None = None,
    transport_factory: TransportFactory | None = None,
) -> int:
    try:
        values = _parser().parse_args(list(arguments))
        if values.authorize_loopback is not True:
            raise LocalModelCLIError("explicit loopback authorization is required")
        host = _pinned_host(values.base_url)
        run_id = RunId.parse(str(UUID(values.run_id)))
        trace_id = TraceId(values.trace_id)
        evaluated_at = _utc_timestamp(values.evaluated_at)
        if not _DIGEST.fullmatch(values.corpus_digest):
            raise LocalModelCLIError("corpus digest is invalid")
        suite = load_benchmark_suite(values.corpus, expected_digest=values.corpus_digest)
        resolver = _resolver(values.credential_ref, environment or {})
        sandbox = WorkspaceSandbox(Path.cwd(), network_hosts=(host,))
        transport = (
            transport_factory(sandbox)
            if transport_factory is not None
            else LoopbackHTTPTransport(sandbox=sandbox)
        )
        adapter = LocalOpenAIAdapter(
            base_url=values.base_url,
            model=values.model,
            credential=values.credential_ref,
            resolver=resolver,
            transport=transport,
        )
        report = await ModelEvaluationRunner(suite).run(
            adapter, run_id=run_id, trace_id=trace_id, evaluated_at=evaluated_at
        )
        manifest = _manifest(
            run_id=run_id,
            trace_id=trace_id,
            model_id=values.model,
            base_url=values.base_url,
            report=report.canonical(),
        )
        output = _write_new(Path(values.output), manifest)
    except (LocalModelCLIError, ValueError, OSError):
        _write(
            stderr,
            {
                "code": "local_evaluation_validation",
                "message": "Local model evaluation was rejected",
            },
        )
        return ExitCode.VALIDATION
    except Exception:
        _write(
            stderr,
            {"code": "local_evaluation_failed", "message": "Local model evaluation failed safely"},
        )
        return ExitCode.EXECUTION
    _write(
        stdout,
        {
            "output": str(output),
            "manifest_digest": manifest["manifest_digest"],
            "report_digest": manifest["report"]["report_digest"],
            "category_results": manifest["report"]["category_results"],
            "qualification_state": "NOT_QUALIFIED",
        },
    )
    return ExitCode.SUCCESS


def _manifest(
    *,
    run_id: RunId,
    trace_id: TraceId,
    model_id: str,
    base_url: str,
    report: Mapping[str, Any],
) -> dict[str, Any]:
    unsigned = {
        "schema_version": "1.0",
        "run_id": str(run_id),
        "trace_id": str(trace_id),
        "provider_id": "local_openai",
        "adapter_version": "1.0",
        "model_id": model_id,
        "endpoint_digest": _sha256(base_url.encode()),
        "report": dict(report),
        "qualification_state": "NOT_QUALIFIED",
    }
    return {**unsigned, "manifest_digest": _sha256(_canonical(unsigned))}


def _resolver(reference: str | None, environment: Mapping[str, str]) -> SecretResolver:
    if reference is None:
        return SecretResolver()
    parsed = SecretReference.parse(reference)
    if parsed.scheme != "env":
        raise LocalModelCLIError("operator CLI currently supports only explicit env references")
    value = environment.get(parsed.locator)
    return SecretResolver(environment={} if value is None else {parsed.locator: value})


def _pinned_host(base_url: str) -> str:
    try:
        parsed = urlsplit(base_url)
    except (TypeError, ValueError) as exc:
        raise LocalModelCLIError("base URL is invalid") from exc
    if parsed.hostname not in _LOOPBACK:
        raise LocalModelCLIError("base URL must use loopback")
    return _LOOPBACK[parsed.hostname]


def _utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise LocalModelCLIError("evaluated_at is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise LocalModelCLIError("evaluated_at must be UTC")
    return parsed


def _write_new(path: Path, manifest: Mapping[str, Any]) -> Path:
    parent = path.parent if str(path.parent) else Path(".")
    if not parent.is_dir() or parent.is_symlink() or path.is_symlink():
        raise LocalModelCLIError("output path is invalid")
    resolved_parent = parent.resolve(strict=True)
    target = resolved_parent / path.name
    if target.exists():
        raise LocalModelCLIError("output already exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(target, flags, 0o600)
    try:
        payload = _canonical(manifest) + b"\n"
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    return target


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _write(stream: TextIO, value: object) -> None:
    stream.write(_canonical(value).decode() + "\n")


def main() -> int:
    return asyncio.run(
        run_local_model_cli(
            sys.argv[1:], stdout=sys.stdout, stderr=sys.stderr, environment=os.environ
        )
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
