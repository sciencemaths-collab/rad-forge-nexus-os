"""Loopback-only bounded HTTP transport for the authenticated Agent application."""

from __future__ import annotations

import asyncio
import json
import re
import socket
import threading
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4

from nexus_os.agent_api import AgentApiRequest, AgentApplication
from nexus_os.domain import TraceId
from nexus_os.operator_auth import OperatorAuthenticator, OperatorAuthError

MAX_REQUEST_BYTES = 1024 * 1024
_LOOPBACK = frozenset({"127.0.0.1", "::1"})
_REQUEST_ID = re.compile(r"^[\x21-\x7e]{1,256}$")


class AgentHttpServerError(ValueError):
    """Safe local HTTP server configuration or request failure."""


class LoginLimiter:
    def __init__(self, maximum: int = 5, window: timedelta = timedelta(minutes=1)) -> None:
        self._maximum = maximum
        self._window = window
        self._attempts: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client: str, now: datetime) -> bool:
        with self._lock:
            values = self._attempts[client]
            cutoff = now - self._window
            while values and values[0] <= cutoff:
                values.popleft()
            if len(values) >= self._maximum:
                return False
            values.append(now)
            return True


class AgentHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        application: AgentApplication,
        authenticator: OperatorAuthenticator,
    ) -> None:
        host, port = address
        if host not in _LOOPBACK or not isinstance(port, int) or not 0 <= port <= 65535:
            raise AgentHttpServerError("Agent server must bind an explicit loopback address")
        self.application = application
        self.authenticator = authenticator
        self.login_limiter = LoginLimiter()
        if host == "::1":
            self.address_family = socket.AF_INET6
        super().__init__(address, AgentHttpRequestHandler)


class AgentHttpRequestHandler(BaseHTTPRequestHandler):
    server: AgentHttpServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _dispatch(self, method: str) -> None:
        now = datetime.now(UTC)
        if not _valid_host(self.headers.get("Host")):
            self._write(421, {"code": "misdirected_request", "message": "Host is not loopback"})
            return
        if self.path == "/healthz" and method == "GET":
            self._write(200, {"status": "ok"})
            return
        if self.path == "/readyz" and method == "GET":
            self._write(200, {"status": "ready"})
            return
        body = self._body()
        if isinstance(body, tuple):
            self._write(*body)
            return
        if self.path == "/v1/auth/login" and method == "POST":
            self._login(body, now)
            return
        request_id = self.headers.get("X-Request-Id", uuid4().hex)
        if not _REQUEST_ID.fullmatch(request_id):
            self._write(400, {"code": "invalid_request", "message": "Request ID is invalid"})
            return
        headers = {
            key: value
            for key in ("Authorization", "Idempotency-Key")
            if (value := self.headers.get(key)) is not None
        }
        request = AgentApiRequest(
            method,
            self.path,
            headers,
            body,
            request_id,
            now,
            TraceId(uuid4().hex),
        )
        response = asyncio.run(self.server.application.handle(request))
        self._write(response.status, response.body, dict(response.headers))

    def _login(self, body: dict[str, Any] | None, now: datetime) -> None:
        client = self.client_address[0]
        if not self.server.login_limiter.allow(client, now):
            self._write(429, {"code": "rate_limited", "message": "Too many login attempts"})
            return
        if body is None or set(body) != {"password"} or not isinstance(body["password"], str):
            self._write(400, {"code": "invalid_request", "message": "Login body is invalid"})
            return
        try:
            issued = self.server.authenticator.login(body["password"], now=now)
        except OperatorAuthError:
            self._write(401, {"code": "unauthorized", "message": "Credentials are invalid"})
            return
        self._write(
            200,
            {
                "access_token": issued.token,
                "token_type": "Bearer",
                "expires_at": issued.expires_at.isoformat().replace("+00:00", "Z"),
                "scopes": sorted(issued.identity.scopes),
            },
            {"Cache-Control": "no-store"},
        )

    def _body(self) -> dict[str, Any] | tuple[int, dict[str, str]] | None:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            return 400, {"code": "invalid_request", "message": "Content-Length is invalid"}
        if length < 0 or length > MAX_REQUEST_BYTES:
            return 413, {"code": "payload_too_large", "message": "Request body is too large"}
        if length == 0:
            return None
        if self.headers.get_content_type() != "application/json":
            return 415, {"code": "unsupported_media_type", "message": "JSON is required"}
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeError, json.JSONDecodeError):
            return 400, {"code": "invalid_request", "message": "JSON body is invalid"}
        if not isinstance(value, dict):
            return 400, {"code": "invalid_request", "message": "JSON object is required"}
        return value

    def _write(
        self,
        status: int,
        body: Any,
        headers: dict[str, str] | None = None,
    ) -> None:
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)


def _valid_host(value: str | None) -> bool:
    if value is None or len(value) > 256:
        return False
    if value.startswith("["):
        closing = value.find("]")
        if closing < 0 or (value[closing + 1 :] and not value[closing + 1 :].startswith(":")):
            return False
        host = value[: closing + 1]
    else:
        host = value.rsplit(":", 1)[0] if value.count(":") == 1 else value
    return host.lower() in {"127.0.0.1", "localhost", "[::1]"}
