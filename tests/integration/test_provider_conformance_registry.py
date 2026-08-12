import asyncio

from nexus_os.conformance import ConformanceHarness, ConformanceStatus
from nexus_os.mock_provider import DeterministicMockAdapter
from nexus_os.providers import (
    ConformanceLevel,
    HealthState,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderRegistry,
)


def test_verified_report_can_bind_mock_descriptor_in_registry() -> None:
    report = asyncio.run(ConformanceHarness().run(DeterministicMockAdapter))
    assert report.status is ConformanceStatus.PASSED

    adapter = DeterministicMockAdapter()
    registry = ProviderRegistry()
    descriptor = ProviderDescriptor(
        "mock",
        "nexus.mock",
        "1.0",
        ProviderCapabilities(frozenset({"stream", "cancel", "deterministic"})),
        ConformanceLevel.MOCK_VERIFIED,
        HealthState.HEALTHY,
    )
    registry.register(descriptor, adapter)

    assert registry.get("mock") is adapter
    assert registry.descriptors()[0].conformance is report.level
