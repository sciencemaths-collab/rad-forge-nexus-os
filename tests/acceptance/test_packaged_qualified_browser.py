import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import Page, expect

from nexus_os.model_attestation import attest_and_qualify
from tests.unit.test_model_attestation import manifest, records
from tests.unit.test_model_registry import QUALIFICATION_ID

PASSWORD = "correct horse battery staple"  # noqa: S105 - inert acceptance fixture


def proposal() -> dict[str, object]:
    return {
        "objective": "Create a reviewed local plan.",
        "mode": "app_build",
        "inputs": [],
        "constraints": ["No external publication."],
        "acceptance_criteria": [
            {
                "acceptance_id": "AC-PLAN_READY",
                "statement": "The plan is reviewable.",
                "verification_method": "runtime_task_evidence",
            }
        ],
        "required_capabilities": ["app_build.planning"],
        "risk_summary": {
            "highest_effect": "WORKSPACE_WRITE",
            "reasons": ["Execution requires separately registered tools."],
        },
        "unresolved_questions": [],
        "review_ready": True,
    }


class QualifiedProvider(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/v1/models":
            self.send_error(404)
            return
        self._json({"object": "list", "data": [{"id": "reference-model"}]})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        json.loads(self.rfile.read(length))
        self._json(
            {
                "id": "qualified-browser-completion",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(proposal())},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            }
        )

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _json(self, body: object) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def _wait_for(url: str, process: subprocess.Popen[bytes]) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise AssertionError("packaged RAD Agent server exited during startup")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:  # noqa: S310 - loopback fixture
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("packaged RAD Agent server did not become healthy")


def _write_configuration(root: Path) -> Path:
    config = root / "config"
    config.mkdir(mode=0o700)
    model_config = config / "models.yaml"
    model_config.write_text(
        "schema_version: '1.0'\nselected: local\nprofiles:\n  local:\n"
        "    type: local_openai\n    base_url: http://127.0.0.1:11434/v1\n"
        "    model: reference-model\n    adapter_version: '1.0'\n",
        encoding="utf-8",
    )
    password = config / "operator-password"
    password.write_text(PASSWORD + "\n", encoding="utf-8")
    os.chmod(password, 0o600)
    evaluation = manifest()
    evidence = records(evaluation)
    attestation = attest_and_qualify(
        evaluation,
        evidence,
        expected_count=7,
        expected_head=evidence[-1].record_hash,
        trusted_producers=frozenset({"independent-evaluator"}),
        qualification_id=QUALIFICATION_ID,
        attested_at=datetime.now(UTC),
        validity_seconds=3600,
    ).to_dict()
    attestation_path = config / "attestation.json"
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    settings = {
        "schema_version": "1.0",
        "mode": "qualified",
        "model_config": str(model_config),
        "password_file": str(password),
        "state_dir": str(config / "state"),
        "attestation": str(attestation_path),
    }
    (config / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return config


def _install_wheel(root: Path) -> Path:
    wheels = tuple((Path(__file__).resolve().parents[2] / "dist").glob("nexus_os-*.whl"))
    assert len(wheels) == 1, "qualified browser acceptance requires exactly one built wheel"
    environment = root / "environment"
    uv = shutil.which("uv")
    assert uv is not None, "qualified browser acceptance requires the locked uv runtime"
    subprocess.run(  # noqa: S603 - resolved trusted uv executable
        (uv, "venv", "--seed", str(environment)),
        check=True,
        cwd=root,
        timeout=180,
    )
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(  # noqa: S603 - fixed interpreter and repository wheel
        (uv, "pip", "install", "--python", str(python), str(wheels[0])),
        check=True,
        cwd=root,
        timeout=180,
    )
    return environment / ("Scripts/rad.exe" if os.name == "nt" else "bin/rad")


def test_packaged_qualified_provider_completes_verified_browser_journey(
    page: Page, tmp_path: Path
) -> None:
    provider = ThreadingHTTPServer(("127.0.0.1", 11434), QualifiedProvider)
    provider_worker = threading.Thread(target=provider.serve_forever)
    provider_worker.start()
    process: subprocess.Popen[bytes] | None = None
    log_root = Path("artifacts/qualified-browser")
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / "server.log"
    try:
        executable = _install_wheel(tmp_path)
        config = _write_configuration(tmp_path)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        port = _free_port()
        with log_path.open("wb") as log:
            process = subprocess.Popen(  # noqa: S603 - fixed installed RAD executable
                (
                    str(executable),
                    "serve",
                    "--config-dir",
                    str(config),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ),
                cwd=tmp_path,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            base_url = f"http://127.0.0.1:{port}"
            _wait_for(base_url + "/healthz", process)
            page.goto(base_url)
            page.locator("#password").fill(PASSWORD)
            page.locator("#login-form button").click()
            page.locator("#project").fill("qualified_browser")
            page.locator("#objective").fill("Create a reviewed local plan.")
            page.locator("#goal-form button").click()
            expect(page.locator("#review")).to_be_visible(timeout=15_000)
            page.locator("#approve").click()
            expect(page.locator("#runtime-setup")).to_be_visible()
            page.locator("#workspace-root").fill(str(workspace))
            page.locator("#runtime-form button").click()
            expect(page.locator("#auto-run")).to_be_enabled(timeout=15_000)
            page.locator("#auto-run").click()
            expect(page.locator("#completion-status")).to_have_text(
                "Verification complete", timeout=30_000
            )
            expect(page.locator("#completion-report")).to_contain_text(
                "LOCAL_VERIFIED_NOT_PRODUCTION"
            )
            expect(page.locator("#chain-status")).to_have_text("VERIFIED")
            assert tuple((workspace / ".rad-agent-artifacts").glob("*.json"))
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        provider.shutdown()
        provider.server_close()
        provider_worker.join(timeout=5)
        assert not provider_worker.is_alive()
