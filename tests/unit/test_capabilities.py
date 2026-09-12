from datetime import UTC, datetime, timedelta

import pytest

from nexus_os.capabilities import (
    CapabilityError,
    CapabilityKind,
    CapabilityManifest,
    CapabilityRegistry,
    NetworkAccess,
    ResourceLimits,
    RouteRequest,
    manifest_from_tool,
)
from nexus_os.domain import ActionEffect
from nexus_os.qualification import CapabilityQualification, CapabilityState
from tests.unit.test_tools import descriptor

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


def manifest(version: str = "1.0.0", *, network: NetworkAccess = NetworkAccess.DENIED):
    return CapabilityManifest(
        capability_id="rad.compute.sum",
        version=version,
        kind=CapabilityKind.ENGINE_OPERATION,
        description="Bounded deterministic sum.",
        operations=("compute.sum",),
        effects=frozenset({ActionEffect.READ_ONLY}),
        deterministic=True,
        network_access=network,
        approval_required=False,
        qualification_required=True,
        resource_limits=ResourceLimits(10, 64),
    )


def qualification(state: CapabilityState = CapabilityState.QUALIFIED, *, expires=None):
    return CapabilityQualification("rad.compute.sum", state, "1.0", NOW, (), (), expires)


def request(**overrides):
    values = {
        "capability_id": "rad.compute.sum",
        "operation": "compute.sum",
        "allowed_effects": frozenset({ActionEffect.READ_ONLY}),
    }
    values.update(overrides)
    return RouteRequest(**values)


def test_manifest_is_canonical_and_native_tools_adapt_without_semantic_weakening() -> None:
    first = manifest()
    second = manifest()
    assert first.canonical() == second.canonical()
    assert first.digest == second.digest

    native = descriptor(effect=ActionEffect.WORKSPACE_WRITE)
    adapted = manifest_from_tool(native)
    assert adapted.kind is CapabilityKind.NATIVE_TOOL
    assert adapted.effects == frozenset({ActionEffect.WORKSPACE_WRITE})
    assert adapted.approval_required == native.approval_required
    assert adapted.resource_limits.timeout_seconds == native.timeout_seconds
    assert adapted.qualification_required is True


def test_registration_is_immutable_and_discovery_is_public_only() -> None:
    registry = CapabilityRegistry()
    implementation = object()
    registry.register(manifest(), implementation, qualification())
    with pytest.raises(CapabilityError, match="already registered"):
        registry.register(manifest(), object(), qualification())

    discovered = registry.discover(operation="compute.sum")
    assert len(discovered) == 1
    assert discovered[0].manifest_digest == manifest().digest
    assert discovered[0].qualification_state is CapabilityState.QUALIFIED
    assert not hasattr(discovered[0], "implementation")


def test_route_requires_exact_qualified_unexpired_allowed_match() -> None:
    registry = CapabilityRegistry()
    chosen = object()
    registry.register(manifest(), chosen, qualification(expires=NOW + timedelta(minutes=1)))
    assert registry.route(request(), at=NOW).implementation is chosen

    for blocked in (
        request(operation="compute.other"),
        request(allowed_effects=frozenset()),
        request(max_timeout_seconds=9),
        request(max_memory_mib=63),
    ):
        with pytest.raises(CapabilityError, match="no eligible"):
            registry.route(blocked, at=NOW)
    with pytest.raises(CapabilityError, match="no eligible"):
        registry.route(request(), at=NOW + timedelta(minutes=1))


def test_route_rejects_ambiguity_and_accepts_exact_version() -> None:
    registry = CapabilityRegistry()
    registry.register(manifest("1.0.0"), object(), qualification())
    registry.register(manifest("2.0.0"), object(), qualification())
    with pytest.raises(CapabilityError, match="ambiguous"):
        registry.route(request(), at=NOW)
    assert registry.route(request(version="2.0.0"), at=NOW).manifest.version == "2.0.0"


def test_invalid_manifest_and_mismatched_qualification_fail_closed() -> None:
    with pytest.raises(CapabilityError, match="version"):
        manifest("latest")
    registry = CapabilityRegistry()
    wrong = CapabilityQualification(
        "other.capability", CapabilityState.QUALIFIED, "1.0", NOW, (), ()
    )
    with pytest.raises(CapabilityError, match="does not match"):
        registry.register(manifest(), object(), wrong)


def test_route_request_rejects_non_finite_or_malformed_constraints() -> None:
    with pytest.raises(CapabilityError, match="timeout"):
        request(max_timeout_seconds=float("nan"))
    with pytest.raises(CapabilityError, match="version"):
        request(version="latest")
    with pytest.raises(CapabilityError, match="network"):
        request(allow_network=1)


def test_qualified_state_with_limitations_or_future_evaluation_is_not_routable() -> None:
    limited = CapabilityQualification(
        "rad.compute.sum",
        CapabilityState.QUALIFIED,
        "1.0",
        NOW,
        (),
        ("manual_limitation",),
    )
    future = CapabilityQualification(
        "rad.compute.sum", CapabilityState.QUALIFIED, "1.0", NOW + timedelta(seconds=1), (), ()
    )
    for value in (limited, future):
        registry = CapabilityRegistry()
        registry.register(manifest(), object(), value)
        with pytest.raises(CapabilityError, match="no eligible"):
            registry.route(request(), at=NOW)
