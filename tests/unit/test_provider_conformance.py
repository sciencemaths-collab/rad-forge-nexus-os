import asyncio
from collections.abc import Coroutine
from typing import Any

from nexus_os.conformance import ConformanceHarness, ConformanceStatus
from nexus_os.mock_provider import DeterministicMockAdapter


def execute[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


def test_mock_passes_complete_deterministic_conformance_suite() -> None:
    report = execute(ConformanceHarness().run(lambda: DeterministicMockAdapter()))

    assert report.status is ConformanceStatus.PASSED
    assert report.level.value == "mock_verified"
    assert report.passed == report.total
    assert report.failed == 0
    assert report.report_digest.startswith("sha256:")
    assert {case.name for case in report.cases} == {
        "health_and_capabilities",
        "successful_lifecycle",
        "cancellation",
        "resume_contract",
        "unknown_task_safety",
    }


def test_report_is_deterministic_and_immutable() -> None:
    harness = ConformanceHarness()
    first = execute(harness.run(lambda: DeterministicMockAdapter()))
    second = execute(harness.run(lambda: DeterministicMockAdapter()))

    assert first == second
    assert first.canonical() == second.canonical()


def test_resume_capability_is_exercised_when_advertised() -> None:
    report = execute(
        ConformanceHarness().run(lambda: DeterministicMockAdapter(supports_resume=True))
    )

    resume = next(case for case in report.cases if case.name == "resume_contract")
    assert resume.status is ConformanceStatus.PASSED
    assert resume.details == ("advertised_and_verified",)
