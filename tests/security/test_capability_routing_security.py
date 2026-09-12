from datetime import UTC, datetime

import pytest

from nexus_os.capabilities import CapabilityError, CapabilityRegistry, NetworkAccess, RouteRequest
from nexus_os.domain import ActionEffect
from tests.unit.test_capabilities import manifest, qualification


def test_registration_never_grants_qualification_or_network_authority() -> None:
    registry = CapabilityRegistry()
    registry.register(manifest(network=NetworkAccess.POLICY_SCOPED), object())
    requested = RouteRequest(
        "rad.compute.sum",
        "compute.sum",
        frozenset({ActionEffect.READ_ONLY}),
        allow_network=True,
    )
    with pytest.raises(CapabilityError, match="no eligible"):
        registry.route(requested, at=datetime(2026, 9, 12, tzinfo=UTC))


def test_network_capability_requires_explicit_network_scope() -> None:
    registry = CapabilityRegistry()
    registry.register(manifest(network=NetworkAccess.POLICY_SCOPED), object(), qualification())
    requested = RouteRequest("rad.compute.sum", "compute.sum", frozenset({ActionEffect.READ_ONLY}))
    with pytest.raises(CapabilityError, match="no eligible"):
        registry.route(requested, at=datetime(2026, 9, 12, tzinfo=UTC))
