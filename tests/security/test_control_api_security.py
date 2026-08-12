import asyncio

from nexus_os.control_api import ApiContext, ApiRequest, ControlApplication, MemoryControlService
from nexus_os.domain import TraceId


def ctx(scopes: frozenset[str]) -> ApiContext:
    return ApiContext("actor", scopes, TraceId("6" * 32))


def test_missing_scope_and_idempotency_key_block_mutation() -> None:
    service = MemoryControlService()
    app = ControlApplication(service)
    request = ApiRequest("POST", "/v1/runs", {}, {"project_id": "p"}, "r1")
    unauthorized = asyncio.run(app.handle(request, ctx(frozenset({"api:read"}))))
    missing_key = asyncio.run(app.handle(request, ctx(frozenset({"api:write"}))))
    assert unauthorized.status == 403
    assert missing_key.status == 400
    assert service.mutation_count == 0


def test_request_cannot_supply_identity_or_trace_and_body_is_bounded() -> None:
    app = ControlApplication(MemoryControlService())
    hostile = ApiRequest(
        "POST",
        "/v1/runs",
        {"Idempotency-Key": "1234567890abcdef"},
        {"project_id": "p", "actor_id": "admin"},
        "r1",
    )
    oversized = ApiRequest(
        "POST",
        "/v1/runs",
        {"Idempotency-Key": "abcdefghijklmnop"},
        {"project_id": "x" * (1024 * 1024 + 1)},
        "r2",
    )
    assert asyncio.run(app.handle(hostile, ctx(frozenset({"api:write"})))).status == 400
    assert asyncio.run(app.handle(oversized, ctx(frozenset({"api:write"})))).status == 413


def test_malformed_path_and_request_id_are_rejected_without_routing() -> None:
    app = ControlApplication(MemoryControlService())
    for path, request_id in (("/v1/runs/../secret", "r1"), ("/v1/runs", "x" * 257)):
        response = asyncio.run(
            app.handle(ApiRequest("GET", path, {}, None, request_id), ctx(frozenset({"api:read"})))
        )
        assert response.status == 400
