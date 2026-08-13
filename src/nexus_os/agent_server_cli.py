"""Executable bootstrap for the loopback NEXUS Agent HTTP server."""

from __future__ import annotations

import argparse
import importlib
import stat
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from nexus_os.agent_api import AgentApplication
from nexus_os.agent_http_server import AgentHttpServer, AgentHttpServerError
from nexus_os.operator_auth import OperatorAuthenticator, OperatorAuthError

ApplicationFactory = Callable[[OperatorAuthenticator, Path], AgentApplication]


class AgentServerCliError(ValueError):
    """Safe command configuration failure."""


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run NEXUS Agent on a local loopback address")
    result.add_argument("--state-dir", required=True, type=Path)
    result.add_argument("--password-file", type=Path)
    result.add_argument(
        "--application-factory",
        default="nexus_os.local_agent_application:create_local_application",
        metavar="MODULE:FUNCTION",
    )
    result.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "::1"))
    result.add_argument("--port", default=8765, type=int)
    return result


def load_factory(reference: str) -> ApplicationFactory:
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute or "." in attribute:
        raise AgentServerCliError("application factory must use MODULE:FUNCTION")
    try:
        candidate = getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError) as exc:
        raise AgentServerCliError("application factory could not be loaded") from exc
    if not callable(candidate):
        raise AgentServerCliError("application factory must be callable")
    return cast(ApplicationFactory, candidate)


def read_bootstrap_password(path: Path) -> str:
    try:
        details = path.stat()
        if not stat.S_ISREG(details.st_mode):
            raise AgentServerCliError("password file must be a regular file")
        if details.st_size > 4096:
            raise AgentServerCliError("password file is too large")
        if details.st_mode & 0o077:
            raise AgentServerCliError("password file must not be accessible by group or others")
        password = path.read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as exc:
        raise AgentServerCliError("password file could not be read") from exc
    if "\n" in password or "\r" in password:
        raise AgentServerCliError("password file must contain one line")
    return password


def run(arguments: Sequence[str] | None = None) -> int:
    values = parser().parse_args(arguments)
    if not 1 <= values.port <= 65535:
        raise AgentServerCliError("port must be from 1 to 65535")
    values.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    authenticator = OperatorAuthenticator(values.state_dir / "operator.sqlite")
    server: AgentHttpServer | None = None
    try:
        if not authenticator.is_bootstrapped():
            if values.password_file is None:
                raise AgentServerCliError("password file is required for first bootstrap")
            authenticator.bootstrap(read_bootstrap_password(values.password_file))
        application = load_factory(values.application_factory)(authenticator, values.state_dir)
        server = AgentHttpServer((values.host, values.port), application, authenticator)
        print(f"NEXUS Agent listening on http://{values.host}:{values.port}", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        if server is not None:
            server.server_close()
        authenticator.close()
    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except (AgentServerCliError, AgentHttpServerError, OperatorAuthError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
