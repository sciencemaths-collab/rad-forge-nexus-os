import asyncio
import json
from datetime import UTC, datetime

import pytest

from nexus_os.agent_api import AgentApiRequest
from nexus_os.domain import TraceId
from nexus_os.local_agent_application import (
    LocalAgentApplicationError,
    create_local_application,
)
from nexus_os.loopback_http_transport import LoopbackHTTPTransport
from nexus_os.model_attestation import attest_and_qualify
from nexus_os.operator_auth import OperatorAuthenticator
from tests.unit.test_model_attestation import manifest, records
from tests.unit.test_model_registry import QUALIFICATION_ID

PASSWORD = "correct horse battery staple"  # noqa: S105 - inert fixture


def proposal():
    return {
        "objective": "Create a reviewed local plan.",
        "mode": "app_build",
        "inputs": [],
        "constraints": ["No external publication."],
        "acceptance_criteria": [
            {
                "acceptance_id": "AC-PLAN_READY",
                "statement": "The plan is reviewable.",
                "verification_method": "manual_review",
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


def configure(tmp_path, monkeypatch):
    model_config = tmp_path / "agent-models.yaml"
    model_config.write_text(
        "schema_version: '1.0'\nselected: local\nprofiles:\n  local:\n"
        "    type: local_openai\n    base_url: http://127.0.0.1:11434/v1\n"
        "    model: reference-model\n",
        encoding="utf-8",
    )
    evaluation_manifest = manifest()
    evidence = records(evaluation_manifest)
    document = attest_and_qualify(
        evaluation_manifest,
        evidence,
        expected_count=7,
        expected_head=evidence[-1].record_hash,
        trusted_producers=frozenset({"independent-evaluator"}),
        qualification_id=QUALIFICATION_ID,
        attested_at=datetime.now(UTC),
        validity_seconds=3600,
    ).to_dict()
    attestation_path = tmp_path / "attestation.json"
    attestation_path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setenv("NEXUS_AGENT_MODEL_CONFIG", str(model_config))
    monkeypatch.setenv("NEXUS_AGENT_MODEL_ATTESTATION", str(attestation_path))


def test_composition_creates_reviewable_session_and_survives_restart(tmp_path, monkeypatch) -> None:
    configure(tmp_path, monkeypatch)

    async def health(self, base_url, api_key, timeout_seconds):
        return True

    async def completion(self, base_url, request, api_key, timeout_seconds):
        return {
            "id": "local-completion-1",
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

    monkeypatch.setattr(LoopbackHTTPTransport, "health", health)
    monkeypatch.setattr(LoopbackHTTPTransport, "create_chat_completion", completion)
    authenticator = OperatorAuthenticator(tmp_path / "operator.sqlite")
    authenticator.bootstrap(PASSWORD)
    issued = authenticator.login(PASSWORD, now=datetime.now(UTC))
    application = create_local_application(authenticator, tmp_path)
    request = AgentApiRequest(
        "POST",
        "/v1/agent/sessions",
        {
            "Authorization": f"Bearer {issued.token}",
            "Idempotency-Key": "create-local-agent-001",
        },
        {"project_id": "local_project", "objective": "Create a reviewed local plan."},
        "request-1",
        datetime.now(UTC),
        TraceId("a" * 32),
    )
    created = asyncio.run(application.handle(request))
    assert created.status == 201 and created.body["state"] == "USER_REVIEW"

    restarted = create_local_application(authenticator, tmp_path)
    replay = asyncio.run(restarted.handle(request))
    assert replay.status == 201 and replay.headers["Idempotent-Replay"] == "true"


def test_missing_configuration_fails_before_application_start(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("NEXUS_AGENT_MODEL_CONFIG", raising=False)
    authenticator = OperatorAuthenticator(tmp_path / "operator.sqlite")
    with pytest.raises(LocalAgentApplicationError, match="MODEL_CONFIG"):
        create_local_application(authenticator, tmp_path)


def test_explicit_development_mode_plans_without_attestation(tmp_path, monkeypatch) -> None:
    model_config = tmp_path / "agent-models.yaml"
    model_config.write_text(
        "schema_version: '1.0'\nselected: local\nprofiles:\n  local:\n"
        "    type: local_openai\n    base_url: http://127.0.0.1:11434/v1\n"
        "    model: reference-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("RAD_AGENT_MODE", "development")
    monkeypatch.setenv("RAD_AGENT_MODEL_CONFIG", str(model_config))
    monkeypatch.delenv("RAD_AGENT_MODEL_ATTESTATION", raising=False)
    monkeypatch.delenv("NEXUS_AGENT_MODEL_ATTESTATION", raising=False)

    async def health(self, base_url, api_key, timeout_seconds):
        return True

    async def completion(self, base_url, request, api_key, timeout_seconds):
        return {
            "id": "development-completion-1",
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

    monkeypatch.setattr(LoopbackHTTPTransport, "health", health)
    monkeypatch.setattr(LoopbackHTTPTransport, "create_chat_completion", completion)
    authenticator = OperatorAuthenticator(tmp_path / "operator.sqlite")
    authenticator.bootstrap(PASSWORD)
    issued = authenticator.login(PASSWORD, now=datetime.now(UTC))
    application = create_local_application(authenticator, tmp_path / "state")
    request = AgentApiRequest(
        "POST",
        "/v1/agent/sessions",
        {
            "Authorization": f"Bearer {issued.token}",
            "Idempotency-Key": "development-agent-001",
        },
        {"project_id": "development_project", "objective": "Create a local plan only."},
        "request-development",
        datetime.now(UTC),
        TraceId("d" * 32),
    )
    created = asyncio.run(application.handle(request))
    assert created.status == 201
    assert created.body["state"] == "USER_REVIEW"
