import json
import os
import shutil
import socket
import subprocess
import threading
import time
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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
        "objective": "Review a protein-interaction hypothesis with traceable evidence.",
        "mode": "research",
        "inputs": [],
        "constraints": [
            "Retain contradictory findings and explicit limitations.",
            "No external publication.",
        ],
        "acceptance_criteria": [
            {
                "acceptance_id": "AC-CLAIM_TRACEABILITY",
                "statement": "Every biological claim links to a source span or artifact.",
                "verification_method": "runtime_task_evidence",
            }
        ],
        "required_capabilities": ["research.planning"],
        "risk_summary": {
            "highest_effect": "WORKSPACE_WRITE",
            "reasons": ["Scientific outputs require evidence and human interpretation."],
        },
        "unresolved_questions": [],
        "review_ready": True,
    }


def task_proposal() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "title": "Qualified task artifact",
        "summary": "Create the exact approved local artifact.",
        "sections": [{"heading": "Scope", "content": "Use the approved task input."}],
        "evidence_notes": ["Verify the typed-tool outcome."],
        "unresolved_questions": [],
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
        request = json.loads(self.rfile.read(length))
        messages = json.dumps(request.get("messages", []))
        output = task_proposal() if "Approved task" in messages else proposal()
        self._json(
            {
                "id": "qualified-browser-completion",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(output)},
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
    with ThreadPoolExecutor(max_workers=1) as executor:
        attestation = executor.submit(_current_attestation).result(timeout=30)
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


def _current_attestation() -> dict[str, object]:
    evaluation = manifest()
    evidence = records(evaluation)
    return attest_and_qualify(
        evaluation,
        evidence,
        expected_count=7,
        expected_head=evidence[-1].record_hash,
        trusted_producers=frozenset({"independent-evaluator"}),
        qualification_id=QUALIFICATION_ID,
        attested_at=datetime.now(UTC),
        validity_seconds=3600,
    ).to_dict()


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
    page: Page, tmp_path: Path, browser_name: str
) -> None:
    diagnostic_root = Path("artifacts/qualified-browser-diagnostics")
    diagnostic_root.mkdir(parents=True, exist_ok=True)
    diagnostic = diagnostic_root / f"{browser_name}.log"
    diagnostic.write_text("stage=start\n", encoding="utf-8")
    provider: ThreadingHTTPServer | None = None
    provider_worker: threading.Thread | None = None
    process: subprocess.Popen[bytes] | None = None
    log_root = Path("artifacts/qualified-browser")
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / "server.log"
    try:
        provider = ThreadingHTTPServer(("127.0.0.1", 11434), QualifiedProvider)
        provider_worker = threading.Thread(target=provider.serve_forever)
        provider_worker.start()
        diagnostic.write_text("stage=provider-started\n", encoding="utf-8")
        executable = _install_wheel(tmp_path)
        diagnostic.write_text("stage=wheel-installed\n", encoding="utf-8")
        config = _write_configuration(tmp_path)
        diagnostic.write_text("stage=qualification-configured\n", encoding="utf-8")
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        research_sources = workspace / "research-sources"
        research_sources.mkdir()
        (research_sources / "protein-study.md").write_text(
            "# Protein interaction\nThe local assay report records binding.\n",
            encoding="utf-8",
        )
        (research_sources / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "sources": [
                        {
                            "path": "protein-study.md",
                            "locator": "doi:10.0000/rad.browser.example",
                            "retrieved_at": "2026-08-16T00:00:00Z",
                            "license_access": "Operator-supplied local acceptance source",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
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
            diagnostic.write_text("stage=rad-server-healthy\n", encoding="utf-8")
            page.goto(base_url)
            diagnostic.write_text("stage=browser-loaded\n", encoding="utf-8")
            page.locator("#password").fill(PASSWORD)
            page.locator("#login-form button").click()
            page.locator("#project").fill("qualified_browser")
            page.locator("#objective").fill(
                "Review a protein-interaction hypothesis with traceable evidence."
            )
            page.locator("#goal-form button").click()
            expect(page.locator("#review")).to_be_visible(timeout=15_000)
            expect(page.locator("#research-review")).to_be_visible()
            expect(page.locator("#research-question")).to_contain_text("protein-interaction")
            expect(page.locator("#research-acceptance")).to_contain_text("AC-CLAIM_TRACEABILITY")
            expect(page.locator("#research-risk")).to_contain_text("WORKSPACE_WRITE")
            expect(page.locator("#research-review")).to_contain_text(
                "External submission or publication is never automatic"
            )
            page.locator("#approve").click()
            expect(page.locator("#runtime-setup")).to_be_visible()
            page.locator("#workspace-root").fill(str(workspace))
            page.locator("#runtime-form button").click()
            expect(page.locator("#auto-run")).to_be_enabled(timeout=15_000)
            expect(page.locator("#task-artifact")).to_contain_text("Qualified task artifact")
            expect(page.locator("#task-artifact-digest")).to_contain_text("sha256:")
            page.locator("#auto-run").click()
            expect(page.locator("#completion-status")).to_have_text(
                "Verification complete", timeout=30_000
            )
            expect(page.locator("#completion-report")).to_contain_text(
                "LOCAL_VERIFIED_NOT_PRODUCTION"
            )
            expect(page.locator("#chain-status")).to_have_text("VERIFIED")
            expect(page.locator("#artifact-count")).not_to_have_text("0 artifacts")
            expect(page.locator("#download-evidence")).to_be_enabled()
            expect(page.locator("#download-report")).to_be_enabled()
            with page.expect_download() as download_info:
                page.locator("#artifact-list button").first.click()
            downloaded = download_info.value
            assert downloaded.suggested_filename.endswith(".json")
            assert downloaded.path().read_bytes().endswith(b"\n")
            assert tuple((workspace / ".rad-agent-artifacts").glob("*.json"))
            sources_artifact = json.loads(
                (workspace / ".rad-agent-artifacts/sources.json").read_text(encoding="utf-8")
            )
            assert sources_artifact["tool"] == "research.ingest_local_sources"
            assert sources_artifact["sources"][0]["locator"].startswith("doi:")
            diagnostic.write_text("stage=verified-completion\n", encoding="utf-8")
    except Exception:
        diagnostic.write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if provider is not None:
            provider.shutdown()
            provider.server_close()
        if provider_worker is not None:
            provider_worker.join(timeout=5)
            assert not provider_worker.is_alive()
