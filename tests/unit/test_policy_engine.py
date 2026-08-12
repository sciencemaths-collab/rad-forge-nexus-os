from nexus_os.domain import ActionEffect
from nexus_os.policy import (
    ActionRequest,
    DataClass,
    Environment,
    PolicyDecisionKind,
    PolicyEngine,
    PolicyRules,
)


def _request(**overrides: object) -> ActionRequest:
    values: dict[str, object] = {
        "actor_id": "runtime",
        "project_id": "project-1",
        "operation": "artifact.read",
        "effect": ActionEffect.READ_ONLY,
        "environment": Environment.LOCAL,
        "data_class": DataClass.INTERNAL,
        "estimated_cost": 0.0,
        "external_communication": False,
        "publishing": False,
        "security_weakening": False,
    }
    values.update(overrides)
    return ActionRequest(**values)  # type: ignore[arg-type]


def test_read_only_local_action_is_allowed() -> None:
    decision = PolicyEngine(PolicyRules()).evaluate(_request())

    assert decision.kind is PolicyDecisionKind.ALLOW
    assert decision.action_digest.startswith("sha256:")
    assert decision.reason_codes == ("policy.allowed",)


def test_workspace_write_can_be_allowed_without_approval() -> None:
    decision = PolicyEngine(PolicyRules()).evaluate(
        _request(operation="artifact.write", effect=ActionEffect.WORKSPACE_WRITE)
    )

    assert decision.kind is PolicyDecisionKind.ALLOW


def test_sensitive_and_destructive_effects_require_approval() -> None:
    engine = PolicyEngine(PolicyRules())

    for effect in (ActionEffect.SENSITIVE, ActionEffect.DESTRUCTIVE):
        decision = engine.evaluate(_request(operation="data.mutate", effect=effect))
        assert decision.kind is PolicyDecisionKind.REQUIRE_APPROVAL
        assert f"effect.{effect.value.lower()}" in decision.reason_codes


def test_high_risk_structured_attributes_always_require_approval() -> None:
    engine = PolicyEngine(PolicyRules())
    requests = (
        _request(environment=Environment.PRODUCTION),
        _request(external_communication=True),
        _request(publishing=True),
        _request(estimated_cost=0.01),
    )

    assert all(
        engine.evaluate(request).kind is PolicyDecisionKind.REQUIRE_APPROVAL
        for request in requests
    )


def test_multiple_reasons_are_canonical_and_digest_is_stable() -> None:
    engine = PolicyEngine(PolicyRules())
    request = _request(
        operation="release.publish",
        effect=ActionEffect.DESTRUCTIVE,
        environment=Environment.PRODUCTION,
        publishing=True,
    )

    first = engine.evaluate(request)
    second = engine.evaluate(request)

    assert first == second
    assert first.reason_codes == tuple(sorted(first.reason_codes))


def test_explicitly_denied_operation_is_blocked() -> None:
    rules = PolicyRules(denied_operations=frozenset({"security.disable"}))
    decision = PolicyEngine(rules).evaluate(
        _request(operation="security.disable", security_weakening=True)
    )

    assert decision.kind is PolicyDecisionKind.DENY
    assert decision.reason_codes == ("operation.denied", "security.weakening")


def test_unlisted_operation_is_denied_when_allowlist_is_configured() -> None:
    rules = PolicyRules(allowed_operations=frozenset({"artifact.read"}))

    decision = PolicyEngine(rules).evaluate(_request(operation="network.call"))

    assert decision.kind is PolicyDecisionKind.DENY
    assert decision.reason_codes == ("operation.not_allowed",)
