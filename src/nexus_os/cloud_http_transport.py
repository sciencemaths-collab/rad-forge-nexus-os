"""Bounded non-redirecting HTTPS transports for official cloud model APIs."""

from __future__ import annotations

import asyncio
import http.client
import json
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

from nexus_os.anthropic_adapter import TransportError as AnthropicTransportError
from nexus_os.openai_adapter import TransportError as OpenAITransportError

_MAX_REQUEST_BYTES = 512_000
_MAX_RESPONSE_BYTES = 2_000_000
_TIMEOUT_MIN = 1
_TIMEOUT_MAX = 300


class HTTPResponseLike(Protocol):
    status: int

    def getheader(self, name: str, default: str | None = None) -> str | None: ...
    def read(self, amount: int | None = None) -> bytes: ...


class HTTPSConnectionLike(Protocol):
    def request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: Mapping[str, str] = {},
    ) -> None: ...

    def getresponse(self) -> HTTPResponseLike: ...
    def close(self) -> None: ...


ConnectionFactory = Callable[[str, int], HTTPSConnectionLike]


class OpenAIHTTPTransport:
    """Official api.openai.com Responses transport with bounded I/O."""

    def __init__(
        self,
        *,
        timeout_seconds: int = 60,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._timeout = _timeout(timeout_seconds)
        self._connection_factory = connection_factory or _connection

    async def health(self, api_key: str) -> bool:
        try:
            status, _ = await asyncio.to_thread(self._request, "GET", "/v1/models", None, api_key)
        except OpenAITransportError:
            return False
        return status == 200

    async def list_models(self, api_key: str) -> tuple[str, ...]:
        status, body = await asyncio.to_thread(self._request, "GET", "/v1/models", None, api_key)
        if status != 200:
            raise OpenAITransportError("OpenAI model discovery returned a non-success status")
        return _models(_decode(body, OpenAITransportError), OpenAITransportError)

    async def create(
        self, request: Mapping[str, object], api_key: str
    ) -> Mapping[str, Any]:
        return await self._json_request("POST", "/v1/responses", request, api_key)

    async def retrieve(self, response_id: str, api_key: str) -> Mapping[str, Any]:
        return await self._json_request("GET", f"/v1/responses/{response_id}", None, api_key)

    async def cancel_response(self, response_id: str, api_key: str) -> Mapping[str, Any]:
        return await self._json_request(
            "POST", f"/v1/responses/{response_id}/cancel", {}, api_key
        )

    async def _json_request(
        self,
        method: str,
        path: str,
        request: Mapping[str, object] | None,
        api_key: str,
    ) -> Mapping[str, Any]:
        body = _encode(request, OpenAITransportError) if request is not None else None
        status, response = await asyncio.to_thread(
            self._request, method, path, body, api_key
        )
        if status != 200:
            raise OpenAITransportError("OpenAI returned a non-success status")
        return _decode(response, OpenAITransportError)

    def _request(
        self, method: str, path: str, body: bytes | None, api_key: str
    ) -> tuple[int, bytes]:
        return _request(
            host="api.openai.com",
            method=method,
            path=path,
            body=body,
            headers={"Authorization": f"Bearer {_credential(api_key, OpenAITransportError)}"},
            timeout=self._timeout,
            connection_factory=self._connection_factory,
            error_type=OpenAITransportError,
        )


class AnthropicHTTPTransport:
    """Official api.anthropic.com Messages transport with bounded I/O."""

    def __init__(
        self,
        *,
        timeout_seconds: int = 60,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._timeout = _timeout(timeout_seconds)
        self._connection_factory = connection_factory or _connection

    async def health(self, api_key: str) -> bool:
        try:
            status, _ = await asyncio.to_thread(self._request, "GET", "/v1/models", None, api_key)
        except AnthropicTransportError:
            return False
        return status == 200

    async def list_models(self, api_key: str) -> tuple[str, ...]:
        status, body = await asyncio.to_thread(self._request, "GET", "/v1/models", None, api_key)
        if status != 200:
            raise AnthropicTransportError("Anthropic model discovery returned a non-success status")
        return _models(_decode(body, AnthropicTransportError), AnthropicTransportError)

    async def create(
        self, request: Mapping[str, object], api_key: str
    ) -> Mapping[str, Any]:
        body = _encode(request, AnthropicTransportError)
        status, response = await asyncio.to_thread(
            self._request, "POST", "/v1/messages", body, api_key
        )
        if status != 200:
            raise AnthropicTransportError("Anthropic returned a non-success status")
        return _decode(response, AnthropicTransportError)

    def _request(
        self, method: str, path: str, body: bytes | None, api_key: str
    ) -> tuple[int, bytes]:
        return _request(
            host="api.anthropic.com",
            method=method,
            path=path,
            body=body,
            headers={
                "x-api-key": _credential(api_key, AnthropicTransportError),
                "anthropic-version": "2023-06-01",
            },
            timeout=self._timeout,
            connection_factory=self._connection_factory,
            error_type=AnthropicTransportError,
        )


def _request(
    *,
    host: str,
    method: str,
    path: str,
    body: bytes | None,
    headers: Mapping[str, str],
    timeout: int,
    connection_factory: ConnectionFactory,
    error_type: type[RuntimeError],
) -> tuple[int, bytes]:
    request_headers = {
        "Accept": "application/json",
        "Connection": "close",
        **headers,
    }
    if body is not None:
        request_headers["Content-Type"] = "application/json"
        request_headers["Content-Length"] = str(len(body))
    connection: HTTPSConnectionLike | None = None
    try:
        connection = connection_factory(host, timeout)
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        content_type = response.getheader("Content-Type", "") or ""
        length = response.getheader("Content-Length")
        if length is not None and (int(length) < 0 or int(length) > _MAX_RESPONSE_BYTES):
            raise error_type("cloud response is oversized")
        payload = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise error_type("cloud response is oversized")
        if response.status == 200 and content_type.lower().split(";", 1)[0] != "application/json":
            raise error_type("cloud response content type is invalid")
        return response.status, payload
    except error_type:
        raise
    except Exception as exc:
        raise error_type("cloud HTTPS transport failed") from exc
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def _encode(value: Mapping[str, object], error_type: type[RuntimeError]) -> bytes:
    try:
        body = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True
        ).encode()
    except (TypeError, ValueError) as exc:
        raise error_type("cloud request is not canonical JSON") from exc
    if not 1 <= len(body) <= _MAX_REQUEST_BYTES:
        raise error_type("cloud request is oversized")
    return body


def _decode(body: bytes, error_type: type[RuntimeError]) -> Mapping[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in items:
            if key in value:
                raise error_type("cloud response contains duplicate JSON keys")
            value[key] = item
        return value

    try:
        value = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                error_type("cloud response contains a non-finite value")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise error_type("cloud response is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise error_type("cloud response JSON must be an object")
    return value


def _models(value: Mapping[str, Any], error_type: type[RuntimeError]) -> tuple[str, ...]:
    data = value.get("data")
    if not isinstance(data, list) or len(data) > 2048:
        raise error_type("cloud model discovery response is invalid")
    identifiers = []
    for item in data:
        identifier = item.get("id") if isinstance(item, Mapping) else None
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 200:
            raise error_type("cloud model discovery response is invalid")
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise error_type("cloud model discovery contains duplicates")
    return tuple(sorted(identifiers))


def _credential(value: str, error_type: type[RuntimeError]) -> str:
    if not isinstance(value, str) or not value or "\r" in value or "\n" in value:
        raise error_type("cloud credential is invalid")
    return value


def _timeout(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not _TIMEOUT_MIN <= value <= _TIMEOUT_MAX
    ):
        raise ValueError("cloud timeout must be from 1 to 300 seconds")
    return value


def _connection(host: str, timeout: int) -> HTTPSConnectionLike:
    return cast(HTTPSConnectionLike, http.client.HTTPSConnection(host, 443, timeout=timeout))
