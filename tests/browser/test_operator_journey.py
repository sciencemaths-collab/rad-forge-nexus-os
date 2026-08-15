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


def preparation() -> dict[str, object]:
    return {
        "task_id": "task-1",
        "task_kind": "mode.app_build.specification",
        "artifact": {"title": "Qualified task proposal"},
        "artifact_digest": "sha256:" + "b" * 64,
        "status": "PROPOSED",
    }


def login_and_resume(page: Page, operator_url: str) -> None:
    page.goto(operator_url)
    page.locator("#password").fill("correct horse battery staple")
    page.locator("#login-form button").click()
    page.locator("#resume-id").fill("session-browser-1")
    page.locator("#resume-form button").click()


def test_first_run_readiness_and_lifecycle_are_explicit(
    page: Page, operator_url: str
) -> None:
    def handle(route: Route) -> None:
        path = route.request.url.split(operator_url, 1)[-1]
        if path == "/v1/auth/login":
            fulfill(route, {"access_token": "browser-token", "token_type": "Bearer"})
        elif path == "/v1/model-qualifications":
            fulfill(route, [{"provider_id": "ollama", "model_id": "qwen-local"}])
        else:
            fulfill(route, {"message": f"unexpected request: {path}"}, status=500)

    page.route("**/v1/**", handle)
    page.goto(operator_url)
    page.locator("#password").fill("correct horse battery staple")
    page.locator("#login-form button").click()

    expect(page.locator("#readiness-status")).to_have_text("Qualified")
    expect(page.locator("#readiness-summary")).to_contain_text("1 active model qualification")
    expect(page.locator("#readiness-detail")).to_contain_text("qwen-local")
    expect(page.locator("#lifecycle [data-state=proposed]")).not_to_have_class("active")


def test_manual_final_step_automatically_verifies_in_real_browser(
    page: Page, operator_url: str
) -> None:
    calls = {"verify": 0}

    def handle(route: Route) -> None:
        request = route.request
        path = request.url.split(operator_url, 1)[-1]
        if path == "/v1/auth/login":
            fulfill(route, {"access_token": "browser-token", "token_type": "Bearer"})
        elif path.endswith("/runtime/preparations"):
            fulfill(route, preparation())
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


def test_interrupted_tick_recovers_durable_completion_without_reexecution(
    page: Page, operator_url: str
) -> None:
    state = {"durable_completed": False, "ticks": 0, "verify": 0}

    def handle(route: Route) -> None:
        path = route.request.url.split(operator_url, 1)[-1]
        if path == "/v1/auth/login":
            fulfill(route, {"access_token": "browser-token", "token_type": "Bearer"})
        elif path.endswith("/runtime/preparations"):
            fulfill(route, preparation())
        elif path.endswith("/runtime/preview"):
            fulfill(route, {"decision": "ALLOW", "approval_required": False})
        elif path.endswith("/runtime/ticks"):
            state["ticks"] += 1
            state["durable_completed"] = True
            route.abort("connectionreset")
        elif path.endswith("/runtime/verify"):
            state["verify"] += 1
            fulfill(route, {"passed": True, "session": {"state": "COMPLETED"}})
        elif path.endswith("/runtime/evidence"):
            fulfill(
                route,
                evidence()
                if state["durable_completed"]
                else {**evidence(), "record_count": 0, "records": []},
            )
        elif path.endswith("/runtime"):
            fulfill(
                route,
                runtime("SUCCEEDED", "SUCCEEDED")
                if state["durable_completed"]
                else runtime("READY", "READY"),
            )
        elif path == "/v1/agent/sessions/session-browser-1":
            fulfill(route, {"state": "COMPLETED" if state["durable_completed"] else "ACTIVE"})
        else:
            fulfill(route, {"message": f"unexpected request: {path}"}, status=500)

    page.route("**/v1/**", handle)
    login_and_resume(page, operator_url)
    page.locator("#tick").click()

    expect(page.locator("#completion-status")).to_have_text("Verification complete")
    expect(page.locator("#completion-report")).to_contain_text("run-browser-1")
    assert state["ticks"] == 1
    assert state["verify"] == 0


def test_terminal_reload_reconstructs_report_without_reverification(
    page: Page, operator_url: str
) -> None:
    calls = {"verify": 0}

    def handle(route: Route) -> None:
        path = route.request.url.split(operator_url, 1)[-1]
        if path == "/v1/auth/login":
            fulfill(route, {"access_token": "browser-token", "token_type": "Bearer"})
        elif path.endswith("/runtime/verify"):
            calls["verify"] += 1
            fulfill(route, {"passed": True, "session": {"state": "COMPLETED"}})
        elif path.endswith("/runtime/evidence"):
            fulfill(route, evidence())
        elif path.endswith("/runtime"):
            fulfill(route, runtime("SUCCEEDED", "SUCCEEDED"))
        elif path == "/v1/agent/sessions/session-browser-1":
            fulfill(route, {"state": "COMPLETED"})
        else:
            fulfill(route, {"message": f"unexpected request: {path}"}, status=500)

    page.route("**/v1/**", handle)
    login_and_resume(page, operator_url)
    expect(page.locator("#completion-status")).to_have_text("Verification complete")
    first_report = page.locator("#completion-report").text_content()

    page.reload()
    page.locator("#password").fill("correct horse battery staple")
    page.locator("#login-form button").click()
    page.locator("#resume-id").fill("session-browser-1")
    page.locator("#resume-form button").click()

    expect(page.locator("#completion-report")).to_have_text(first_report or "")
    assert calls["verify"] == 0


def test_operator_surface_has_no_critical_accessibility_structure_failures(
    page: Page, operator_url: str
) -> None:
    page.goto(operator_url)
    audit = page.evaluate(
        """() => {
          const failures = [];
          if (document.documentElement.lang !== 'en') failures.push('document-language');
          if (!document.querySelector('main')) failures.push('main-landmark');
          if (document.querySelectorAll('h1').length !== 1) failures.push('single-h1');
          if (!document.querySelector('[role="status"][aria-live]')) failures.push('live-status');
          for (const input of document.querySelectorAll('input,textarea')) {
            if (!input.labels || input.labels.length === 0) failures.push(`unlabelled:${input.id}`);
          }
          for (const button of document.querySelectorAll('button')) {
            const name = button.getAttribute('aria-label') || button.textContent.trim();
            if (!name) failures.push('unnamed-button');
          }
          return failures;
        }"""
    )
    assert audit == []

    page.keyboard.press("Tab")
    expect(page.locator("#password")).to_be_focused()
    assert page.locator("#password").evaluate(
        "element => getComputedStyle(element).outlineStyle !== 'none'"
    )
