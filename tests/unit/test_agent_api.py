import asyncio
import json

from nexus_os.agent_api import (
    AgentApiRequest,
    AgentApplication,
    AgentApplicationService,
    AgentIdentity,
    DurableReplayStore,
)
from nexus_os.agent_controller import AgentReasoningController
from nexus_os.agent_store import AgentSessionStore
from nexus_os.domain import TraceId
from nexus_os.model_registry import ModelQualificationRegistry
from tests.unit.test_agent_controller import CONTROL_AT, Adapter, Ids, proposal
from tests.unit.test_agent_store import SESSION_ID, uid
from tests.unit.test_model_registry import REGISTERED_AT, attestation


class Auth:
    def authenticate(self, token):
        if token == "valid-token-123456":  # noqa: S105 - inert authenticator fixture
            return AgentIdentity(
                "owner-user",
                frozenset(
                    {"agent:read", "agent:write", "agent:approve", "model-qualifications:read"}
                ),
                True,
            )
        if token == "service-token-1234":  # noqa: S105 - inert authenticator fixture
            return AgentIdentity("service-agent", frozenset({"agent:read", "agent:write"}), False)
        return None


class AppIds:
    def __init__(self):
        self.number = 200

    def session_id(self):
        return SESSION_ID

    def event_id(self):
        self.number += 1
        return uid(self.number)


def app(tmp_path, outputs):
    sessions = AgentSessionStore(tmp_path / "sessions.sqlite")
    registry = ModelQualificationRegistry(tmp_path / "models.sqlite")
    registry.register(
        attestation(), registered_at=REGISTERED_AT, registered_by="release-controller"
    )
    controller = AgentReasoningController(
        sessions=sessions,
        qualifications=registry,
        adapter=Adapter(outputs),
        provider_id="local_openai",
        model_id="reference-model",
        adapter_version="1.0",
        ids=Ids(),
    )
    service = AgentApplicationService(
        sessions=sessions, controller=controller, qualifications=registry, ids=AppIds()
    )
    return AgentApplication(
        authenticator=Auth(),
        service=service,
        replays=DurableReplayStore(tmp_path / "replays.sqlite"),
    ), sessions


def request(
    method,
    path,
    *,
    body=None,
    key=None,
    token="valid-token-123456",  # noqa: S107 - inert authenticator fixture
    request_id="r1",
):
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return AgentApiRequest(method, path, headers, body, request_id, CONTROL_AT, TraceId("8" * 32))


def test_create_read_candidate_and_human_approve(tmp_path) -> None:
    subject, _ = app(tmp_path, [json.dumps(proposal())])
    created = asyncio.run(
        subject.handle(
            request(
                "POST",
                "/v1/agent/sessions",
                body={"project_id": "reference_agent", "objective": "Build a reviewed app."},
                key="create-session-0001",
            )
        )
    )
    assert created.status == 201 and created.body["state"] == "USER_REVIEW"
    candidate = asyncio.run(
        subject.handle(request("GET", f"/v1/agent/sessions/{SESSION_ID}/candidate"))
    )
    approved = asyncio.run(
        subject.handle(
            request(
                "POST",
                f"/v1/agent/sessions/{SESSION_ID}/approve",
                body={"candidate_digest": candidate.body["candidate_digest"]},
                key="approve-session-001",
            )
        )
    )
    assert candidate.status == 200
    assert approved.status == 200 and approved.body["state"] == "APPROVED"


def test_authentication_scope_and_human_approval_are_enforced(tmp_path) -> None:
    subject, _ = app(tmp_path, [json.dumps(proposal())])
    missing = asyncio.run(
        subject.handle(
            request("GET", "/v1/model-qualifications", token="bad-token-0000000")  # noqa: S106
        )
    )
    forbidden = asyncio.run(
        subject.handle(
            request("GET", "/v1/model-qualifications", token="service-token-1234")  # noqa: S106
        )
    )
    assert missing.status == 401
    assert forbidden.status == 403


def test_mutation_replay_survives_application_restart(tmp_path) -> None:
    subject, _ = app(tmp_path, [json.dumps(proposal())])
    req = request(
        "POST",
        "/v1/agent/sessions",
        body={"project_id": "reference_agent", "objective": "Build a reviewed app."},
        key="create-session-0001",
    )
    first = asyncio.run(subject.handle(req))
    second = asyncio.run(subject.handle(req))
    assert second.status == first.status
    assert second.body == first.body
    assert second.headers["Idempotent-Replay"] == "true"


def test_idempotency_key_is_bound_to_canonical_request(tmp_path) -> None:
    subject, _ = app(tmp_path, [json.dumps(proposal())])
    asyncio.run(
        subject.handle(
            request(
                "POST",
                "/v1/agent/sessions",
                body={"project_id": "reference_agent", "objective": "Build a reviewed app."},
                key="create-session-0001",
            )
        )
    )
    conflict = asyncio.run(
        subject.handle(
            request(
                "POST",
                "/v1/agent/sessions",
                body={"project_id": "reference_agent", "objective": "Different objective."},
                key="create-session-0001",
            )
        )
    )
    assert conflict.status == 409 and conflict.body["code"] == "idempotency_conflict"


def test_missing_key_secret_body_and_unknown_route_fail_safely(tmp_path) -> None:
    subject, sessions = app(tmp_path, [json.dumps(proposal())])
    no_key = asyncio.run(
        subject.handle(
            request(
                "POST",
                "/v1/agent/sessions",
                body={"project_id": "reference_agent", "objective": "Build."},
            )
        )
    )
    secret = asyncio.run(
        subject.handle(
            request(
                "POST",
                "/v1/agent/sessions",
                body={
                    "project_id": "reference_agent",
                    "objective": "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
                },
                key="create-session-0001",
            )
        )
    )
    missing = asyncio.run(subject.handle(request("GET", "/v1/agent/unknown")))
    assert (no_key.status, secret.status, missing.status) == (400, 400, 404)
    try:
        sessions.get(SESSION_ID)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid requests mutated session state")
