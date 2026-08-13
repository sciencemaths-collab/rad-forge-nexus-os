"""Bounded standard-library HTTP transport for local OpenAI-compatible servers."""

from __future__ import annotations

import asyncio
import http.client
import json
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

from nexus_os.local_openai_adapter import TransportError
from nexus_os.sandbox import SandboxError, WorkspaceSandbox

_MAX_REQUEST_BYTES = 512_000
_MAX_RESPONSE_BYTES = 2_000_000
_LOOPBACK = {"localhost": "127.0.0.1", "127.0.0.1": "127.0.0.1", "::1": "::1"}


class HTTPResponseLike(Protocol):
    status: int

    def getheader(self, name: str, default: str | None = None) -> str | None: ...
    def read(self, amount: int | None = None) -> bytes: ...


class HTTPConnectionLike(Protocol):
    def request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: Mapping[str, str] = {},
    ) -> None: ...

    def getresponse(self) -> HTTPResponseLike: ...
    def close(self) -> None: ...


ConnectionFactory = Callable[[str, str, int, int], HTTPConnectionLike]


class LoopbackHTTPTransport:
    """Make authorized non-redirecting requests to one explicit loopback server."""

    def __init__(
        self,
        *,
        sandbox: WorkspaceSandbox,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        if not isinstance(sandbox, WorkspaceSandbox):
            raise TransportError("loopback transport requires an explicit network sandbox")
        self._sandbox = sandbox
        self._connection_factory = connection_factory or _stdlib_connection

    async def health(self, base_url: str, api_key: str | None, timeout_seconds: int) -> bool:
        try:
            status, _ = await asyncio.to_thread(
                self._request,
                base_url,
                "GET",
                "/v1/models",
                None,
                api_key,
                timeout_seconds,
            )
        except TransportError:
            return False
        return status == 200

    async def list_models(
        self, base_url: str, api_key: str | None, timeout_seconds: int
    ) -> tuple[str, ...]:
        status, body = await asyncio.to_thread(
            self._request, base_url, "GET", "/v1/models", None, api_key, timeout_seconds
        )
        if status != 200:
            raise TransportError("local provider model discovery returned a non-success status")
        value = _decode_json_object(body)
        models = value.get("data")
        if not isinstance(models, list) or len(models) > 1024:
            raise TransportError("local provider model discovery response is invalid")
        identifiers: list[str] = []
        for item in models:
            if not isinstance(item, Mapping) or set(item) - {"id", "object", "created", "owned_by"}:
                raise TransportError("local provider model discovery response is invalid")
            identifier = item.get("id")
            if not isinstance(identifier, str) or not 1 <= len(identifier) <= 200:
                raise TransportError("local provider model discovery response is invalid")
            identifiers.append(identifier)
        if len(identifiers) != len(set(identifiers)):
            raise TransportError("local provider model discovery contains duplicates")
        return tuple(sorted(identifiers))

    async def create_chat_completion(
        self,
        base_url: str,
        request: Mapping[str, object],
        api_key: str | None,
        timeout_seconds: int,
    ) -> Mapping[str, Any]:
        try:
            body = json.dumps(
                request,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                ensure_ascii=True,
            ).encode()
        except (TypeError, ValueError) as exc:
            raise TransportError("local request is not canonical JSON") from exc
        if not 1 <= len(body) <= _MAX_REQUEST_BYTES:
            raise TransportError("local request is oversized")
        status, response_body = await asyncio.to_thread(
            self._request,
            base_url,
            "POST",
            "/v1/chat/completions",
            body,
            api_key,
            timeout_seconds,
        )
        if status != 200:
            raise TransportError("local provider returned a non-success status")
        return _decode_json_object(response_body)

    def _request(
        self,
        base_url: str,
        method: str,
        path: str,
        body: bytes | None,
        api_key: str | None,
        timeout_seconds: int,
    ) -> tuple[int, bytes]:
        scheme, host, port = _endpoint(base_url)
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 1 <= timeout_seconds <= 300
        ):
            raise TransportError("local transport timeout must be from 1 to 300")
        if api_key is not None and (
            not isinstance(api_key, str) or not api_key or "\r" in api_key or "\n" in api_key
        ):
            raise TransportError("local transport credential is invalid")
        try:
            self._sandbox.authorize_host(host, port=port)
        except SandboxError as exc:
            raise TransportError("loopback network access is not authorized") from exc
        headers = {"Accept": "application/json", "Connection": "close"}
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
        if api_key is not None:
            headers["Authorization"] = f"Bearer {api_key}"
        connection: HTTPConnectionLike | None = None
        try:
            connection = self._connection_factory(scheme, host, port, timeout_seconds)
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            content_type = response.getheader("Content-Type", "") or ""
            content_length = response.getheader("Content-Length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as exc:
                    raise TransportError("local response content length is invalid") from exc
                if declared_length < 0 or declared_length > _MAX_RESPONSE_BYTES:
                    raise TransportError("local response is oversized")
            response_body = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(response_body) > _MAX_RESPONSE_BYTES:
                raise TransportError("local response is oversized")
            if (
                response.status == 200
                and not content_type.lower().split(";", 1)[0].strip() == "application/json"
            ):
                raise TransportError("local response content type is invalid")
            return response.status, response_body
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError("local HTTP transport failed") from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    connection = None


def _endpoint(base_url: str) -> tuple[str, str, int]:
    try:
        parsed = urlsplit(base_url)
        raw_host = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise TransportError("local transport endpoint is invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or raw_host not in _LOOPBACK
        or port is None
        or parsed.path.rstrip("/") != "/v1"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise TransportError("local transport requires an explicit loopback /v1 endpoint")
    return parsed.scheme, _LOOPBACK[raw_host], port


def _stdlib_connection(scheme: str, host: str, port: int, timeout: int) -> HTTPConnectionLike:
    connection_type = (
        http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
    )
    return cast(HTTPConnectionLike, connection_type(host, port, timeout=timeout))


def _decode_json_object(body: bytes) -> Mapping[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise TransportError("local response contains duplicate JSON keys")
            result[key] = value
        return result

    try:
        decoded = body.decode("utf-8")
        value = json.loads(decoded, object_pairs_hook=pairs, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportError("local response is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise TransportError("local response JSON must be an object")
    return value


def _reject_constant(value: str) -> None:
    raise TransportError("local response contains a non-finite JSON value")
