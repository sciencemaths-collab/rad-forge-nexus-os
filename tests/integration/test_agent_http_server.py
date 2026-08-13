import http.client
import json
import threading

import pytest

from nexus_os.agent_api import AgentApiResponse
from nexus_os.agent_http_server import AgentHttpServer, AgentHttpServerError
from nexus_os.operator_auth import OperatorAuthenticator

PASSWORD = "correct horse battery staple"  # noqa: S105 - inert local test fixture


class Application:
    async def handle(self, request):
        authorization = request.headers.get("Authorization", "")
        token = authorization.removeprefix("Bearer ")
        if self.authenticator.authenticate(token) is None:
            return AgentApiResponse(401, {"code": "unauthorized"})
        return AgentApiResponse(200, [{"model_id": "local-test"}])


def request(connection, method, path, body=None, headers=None):
    encoded = None if body is None else json.dumps(body)
    actual_headers = dict(headers or {})
    if encoded is not None:
        actual_headers["Content-Type"] = "application/json"
    connection.request(method, path, body=encoded, headers=actual_headers)
    response = connection.getresponse()
    return response.status, dict(response.getheaders()), json.loads(response.read())


def test_health_login_and_authenticated_request_over_real_socket(tmp_path) -> None:
    authenticator = OperatorAuthenticator(tmp_path / "operator.sqlite")
    authenticator.bootstrap(PASSWORD)
    application = Application()
    application.authenticator = authenticator
    server = AgentHttpServer(("127.0.0.1", 0), application, authenticator)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        status, headers, body = request(connection, "GET", "/healthz")
        assert status == 200 and body == {"status": "ok"}
        assert headers["Cache-Control"] == "no-store"

        status, _, body = request(connection, "POST", "/v1/auth/login", {"password": PASSWORD})
        assert status == 200 and body["token_type"] == "Bearer"  # noqa: S105
        token = body["access_token"]

        status, _, body = request(
            connection,
            "GET",
            "/v1/model-qualifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200 and body == [{"model_id": "local-test"}]
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        authenticator.close()
    assert not worker.is_alive()


def test_wrong_host_oversized_body_and_login_rate_limit_fail_closed(tmp_path) -> None:
    authenticator = OperatorAuthenticator(tmp_path / "operator.sqlite")
    authenticator.bootstrap(PASSWORD)
    application = Application()
    application.authenticator = authenticator
    server = AgentHttpServer(("127.0.0.1", 0), application, authenticator)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        status, _, _ = request(connection, "GET", "/healthz", headers={"Host": "evil.test"})
        assert status == 421
        connection.request(
            "POST",
            "/v1/auth/login",
            headers={"Content-Type": "application/json", "Content-Length": str(1024 * 1024 + 1)},
        )
        response = connection.getresponse()
        assert response.status == 413
        response.read()
        connection.close()

        for attempt in range(6):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            status, _, _ = request(
                connection, "POST", "/v1/auth/login", {"password": "wrong password value"}
            )
            assert status == (401 if attempt < 5 else 429)
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        authenticator.close()


def test_non_loopback_bind_is_rejected_before_socket_creation(tmp_path) -> None:
    authenticator = OperatorAuthenticator(tmp_path / "operator.sqlite")
    with pytest.raises(AgentHttpServerError, match="loopback"):
        AgentHttpServer(("0.0.0.0", 8765), Application(), authenticator)  # noqa: S104
    authenticator.close()
