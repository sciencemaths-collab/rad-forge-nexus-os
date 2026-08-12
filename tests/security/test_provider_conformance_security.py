import asyncio
from collections.abc import AsyncIterator, Coroutine
from typing import Any

from nexus_os.conformance import ConformanceHarness, ConformanceStatus
from nexus_os.mock_provider import DeterministicMockAdapter
from nexus_os.providers import ProviderEvent, ProviderTask


def execute[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


class BrokenSequenceAdapter(DeterministicMockAdapter):
    async def stream_events(self, provider_task_id: str) -> AsyncIterator[ProviderEvent]:
        events = [event async for event in super().stream_events(provider_task_id)]
        for event in events[1:]:
            yield event


class LeakingIdentityAdapter(DeterministicMockAdapter):
    async def run(self, task: ProviderTask) -> str:
        await super().run(task)
        return "different-provider-task"


class HangingHealthAdapter(DeterministicMockAdapter):
    async def healthcheck(self):  # type: ignore[no-untyped-def]
        await asyncio.Event().wait()


def test_malformed_event_sequence_fails_closed() -> None:
    report = execute(ConformanceHarness(timeout_seconds=0.1).run(BrokenSequenceAdapter))

    assert report.status is ConformanceStatus.FAILED
    case = next(item for item in report.cases if item.name == "successful_lifecycle")
    assert case.status is ConformanceStatus.FAILED
    assert "sequence" in case.details[0]


def test_provider_identity_mismatch_fails_without_leaking_task_input() -> None:
    report = execute(ConformanceHarness(timeout_seconds=0.1).run(LeakingIdentityAdapter))

    assert report.status is ConformanceStatus.FAILED
    serialized = str(report.canonical())
    assert "CONFORMANCE_SECRET_CANARY" not in serialized
    assert "identity" in serialized


def test_timeout_is_bounded_and_reported_safely() -> None:
    report = execute(ConformanceHarness(timeout_seconds=0.01).run(HangingHealthAdapter))

    assert report.status is ConformanceStatus.FAILED
    case = next(item for item in report.cases if item.name == "health_and_capabilities")
    assert case.details == ("operation timed out",)


def test_invalid_harness_bounds_are_rejected() -> None:
    for value in (0, -1, 301, float("nan")):
        try:
            ConformanceHarness(timeout_seconds=value)  # type: ignore[arg-type]
        except ValueError as error:
            assert "timeout" in str(error)
        else:
            raise AssertionError("invalid timeout was accepted")
