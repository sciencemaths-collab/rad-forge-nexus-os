import asyncio

from nexus_os.control_api import ApiContext, ApiRequest, ControlApplication, MemoryControlService
from nexus_os.domain import TraceId


def context() -> ApiContext:
    return ApiContext("actor", frozenset({"api:read", "api:write"}), TraceId("5" * 32))


def test_create_and_get_run_follow_openapi_status_and_shape() -> None:
    app = ControlApplication(MemoryControlService())
    created = asyncio.run(
        app.handle(
            ApiRequest(
                "POST",
                "/v1/runs",
                {"Idempotency-Key": "1234567890abcdef"},
                {"project_id": "project-1"},
                "request-1",
            ),
            context(),
        )
    )
    assert created.status == 202
    assert created.body["project_id"] == "project-1"
    assert created.body["state"] == "SPECIFYING"

    fetched = asyncio.run(
        app.handle(
            ApiRequest("GET", f"/v1/runs/{created.body['run_id']}", {}, None, "request-2"),
            context(),
        )
    )
    assert fetched.status == 200
    assert fetched.body == created.body


def test_mutation_replay_is_bound_to_request_and_calls_service_once() -> None:
    service = MemoryControlService()
    app = ControlApplication(service)
    request = ApiRequest(
        "POST",
        "/v1/runs",
        {"Idempotency-Key": "1234567890abcdef"},
        {"project_id": "project-1"},
        "request-1",
    )
    first = asyncio.run(app.handle(request, context()))
    second = asyncio.run(app.handle(request, context()))
    assert first.body == second.body
    assert second.headers["Idempotent-Replay"] == "true"
    assert service.mutation_count == 1

    changed = ApiRequest(
        "POST",
        "/v1/runs",
        {"Idempotency-Key": "1234567890abcdef"},
        {"project_id": "different"},
        "request-3",
    )
    conflict = asyncio.run(app.handle(changed, context()))
    assert conflict.status == 409
    assert conflict.body["code"] == "idempotency_conflict"


def test_unknown_route_and_invalid_body_use_stable_error_envelope() -> None:
    app = ControlApplication(MemoryControlService())
    missing = asyncio.run(app.handle(ApiRequest("GET", "/v1/unknown", {}, None, "r1"), context()))
    invalid = asyncio.run(
        app.handle(
            ApiRequest(
                "POST",
                "/v1/runs",
                {"Idempotency-Key": "1234567890abcdef"},
                {"project_id": "p", "extra": True},
                "r2",
            ),
            context(),
        )
    )
    assert missing.status == 404
    assert invalid.status == 400
    assert set(invalid.body) == {"code", "message", "request_id", "retryable"}
