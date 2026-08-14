import json
import threading

import pytest
from playwright.sync_api import Page, Route, expect

from nexus_os.agent_api import AgentApiResponse
from nexus_os.agent_http_server import AgentHttpServer
from nexus_os.operator_auth import OperatorAuthenticator


class UnusedApplication:
    async def handle(self, request):
        del request
        return AgentApiResponse(500, {"message": "browser fixture did not intercept request"})


@pytest.fixture
def operator_url(tmp_path):
    authenticator = OperatorAuthenticator(tmp_path / "operator.sqlite")
    application = UnusedApplication()
    server = AgentHttpServer(("127.0.0.1", 0), application, authenticator)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        authenticator.close()


def fulfill(route: Route, body: object, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(body),
    )


def runtime(state: str, task_state: str) -> dict[str, object]:
    return {
        "run_id": "run-browser-1",
        "run_state": state,
        "task_states": {"task-1": task_state},
    }


def evidence() -> dict[str, object]:
    return {
        "run_id": "run-browser-1",
        "record_count": 1,
        "chain_status": "VERIFIED",
        "head_hash": "sha256:" + "a" * 64,
        "records": [{"record_type": "runtime_task_evidence"}],
    }


def login_and_resume(page: Page, operator_url: str) -> None:
    page.goto(operator_url)
    page.locator("#password").fill("correct horse battery staple")
    page.locator("#login-form button").click()
    page.locator("#resume-id").fill("session-browser-1")
    page.locator("#resume-form button").click()


def test_manual_final_step_automatically_verifies_in_real_browser(
    page: Page, operator_url: str
) -> None:
    calls = {"verify": 0}

    def handle(route: Route) -> None:
        request = route.request
        path = request.url.split(operator_url, 1)[-1]
        if path == "/v1/auth/login":
            fulfill(route, {"access_token": "browser-token", "token_type": "Bearer"})
        elif path.endswith("/runtime/preview"):
            fulfill(route, {"decision": "ALLOW", "approval_required": False})
        elif path.endswith("/runtime/ticks"):
            fulfill(route, {"outcome": "SUCCEEDED", "runtime": runtime("SUCCEEDED", "SUCCEEDED")})
        elif path.endswith("/runtime/verify"):
            calls["verify"] += 1
            fulfill(route, {"passed": True, "session": {"state": "COMPLETED"}})
        elif path.endswith("/runtime/evidence"):
            fulfill(route, evidence())
        elif path.endswith("/runtime"):
            fulfill(route, runtime("READY", "READY"))
        elif path == "/v1/agent/sessions/session-browser-1":
            fulfill(route, {"state": "ACTIVE"})
        else:
            fulfill(route, {"message": f"unexpected request: {path}"}, status=500)

    page.route("**/v1/**", handle)
    login_and_resume(page, operator_url)
    expect(page.locator("#tick")).to_be_enabled()
    page.locator("#tick").click()

    expect(page.locator("#completion-status")).to_have_text("Verification complete")
    expect(page.locator("#completion-report")).to_contain_text("LOCAL_VERIFIED_NOT_PRODUCTION")
    expect(page.locator("#chain-status")).to_have_text("VERIFIED")
    assert calls["verify"] == 1


def test_failed_resume_never_shows_success_qualification(page: Page, operator_url: str) -> None:
    def handle(route: Route) -> None:
        path = route.request.url.split(operator_url, 1)[-1]
        if path == "/v1/auth/login":
            fulfill(route, {"access_token": "browser-token", "token_type": "Bearer"})
        elif path.endswith("/runtime/evidence"):
            fulfill(route, evidence())
        elif path.endswith("/runtime"):
            fulfill(route, runtime("FAILED", "FAILED"))
        elif path == "/v1/agent/sessions/session-browser-1":
            fulfill(route, {"state": "FAILED"})
        else:
            fulfill(route, {"message": f"unexpected request: {path}"}, status=500)

    page.route("**/v1/**", handle)
    login_and_resume(page, operator_url)

    expect(page.locator("#completion-status")).to_have_text("Run failed")
    expect(page.locator("#completion-title")).to_have_text("Failed run report")
    expect(page.locator("#completion-report")).not_to_contain_text("LOCAL_VERIFIED_NOT_PRODUCTION")
    expect(page.locator("#completion-report")).to_contain_text('"verification_passed": false')


def test_evidence_integrity_failure_hides_completion(page: Page, operator_url: str) -> None:
    def handle(route: Route) -> None:
        path = route.request.url.split(operator_url, 1)[-1]
        if path == "/v1/auth/login":
            fulfill(route, {"access_token": "browser-token", "token_type": "Bearer"})
        elif path.endswith("/runtime/evidence"):
            fulfill(route, {"message": "evidence chain integrity verification failed"}, status=500)
        elif path.endswith("/runtime"):
            fulfill(route, runtime("SUCCEEDED", "SUCCEEDED"))
        else:
            fulfill(route, {"message": f"unexpected request: {path}"}, status=500)

    page.route("**/v1/**", handle)
    login_and_resume(page, operator_url)

    expect(page.locator("#chain-status")).to_have_text("INVALID")
    expect(page.locator("#evidence-list")).to_contain_text("integrity verification failed")
    expect(page.locator("#completion")).to_be_hidden()
