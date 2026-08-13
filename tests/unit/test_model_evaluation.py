import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from nexus_os.domain import RunId, TraceId
from nexus_os.local_openai_adapter import LocalOpenAIAdapter, LocalOpenAITransport
from nexus_os.model_evaluation import (
    ModelEvaluationCase,
    ModelEvaluationError,
    ModelEvaluationRunner,
    ModelEvaluationSuite,
)
from nexus_os.model_qualification import EvaluationCategory, EvaluationResult
from nexus_os.secrets import SecretResolver

NOW = datetime(2026, 8, 13, 14, tzinfo=UTC)
RUN_ID = RunId.parse("30000000-0000-4000-8000-000000000001")
TRACE_ID = TraceId("3" * 32)


def suite(*, two_schema_cases: bool = False) -> ModelEvaluationSuite:
    cases = [
        ModelEvaluationCase(
            f"{category.value}.v1", category, f"Evaluate {category.value}", {"safe": True}
        )
        for category in EvaluationCategory
    ]
    if two_schema_cases:
        cases.append(
            ModelEvaluationCase(
                "schema_conformance.v2",
                EvaluationCategory.SCHEMA_CONFORMANCE,
                "Evaluate schema again",
                {"safe": True},
            )
        )
    return ModelEvaluationSuite.create("1.0", tuple(cases))


class ScriptedTransport(LocalOpenAITransport):
    def __init__(self, outputs: list[str]) -> None:
        self.responses = [
            {
                "id": f"completion-{index}",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": output},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            for index, output in enumerate(outputs, start=1)
        ]

    async def health(self, base_url, api_key, timeout_seconds):  # type: ignore[no-untyped-def]
        return True

    async def create_chat_completion(  # type: ignore[no-untyped-def]
        self, base_url, request, api_key, timeout_seconds
    ):
        return self.responses.pop(0)


def adapter(outputs: list[str]) -> LocalOpenAIAdapter:
    transport = ScriptedTransport(outputs)
    return LocalOpenAIAdapter(
        base_url="http://127.0.0.1:11434/v1",
        model="fixture",
        credential=None,
        resolver=SecretResolver(),
        transport=transport,
    )


def execute(test_suite: ModelEvaluationSuite, outputs: list[str]):
    return asyncio.run(
        ModelEvaluationRunner(test_suite).run(
            adapter(outputs), run_id=RUN_ID, trace_id=TRACE_ID, evaluated_at=NOW
        )
    )


def test_all_exact_structured_outputs_pass_every_category() -> None:
    report = execute(suite(), [json.dumps({"safe": True})] * 7)
    assert set(report.category_results.values()) == {EvaluationResult.PASS}
    assert report.report_digest.startswith("sha256:")
    assert all("safe" not in str(item.canonical()) for item in report.observations)


def test_partial_category_pass_is_limited_and_no_pass_is_fail() -> None:
    test_suite = suite(two_schema_cases=True)
    failing_schema_outputs = [
        json.dumps({"safe": case.category is not EvaluationCategory.SCHEMA_CONFORMANCE})
        for case in test_suite.cases
    ]
    report = execute(
        test_suite,
        failing_schema_outputs,
    )
    assert report.category_results[EvaluationCategory.SCHEMA_CONFORMANCE] is EvaluationResult.FAIL

    outputs = [json.dumps({"safe": True})] * 8
    schema_index = next(
        index
        for index, case in enumerate(test_suite.cases)
        if case.category is EvaluationCategory.SCHEMA_CONFORMANCE
    )
    outputs[schema_index] = json.dumps({"safe": False})
    limited = execute(test_suite, outputs)
    assert (
        limited.category_results[EvaluationCategory.SCHEMA_CONFORMANCE] is EvaluationResult.LIMITED
    )


def test_suite_digest_is_order_independent_and_binds_corpus() -> None:
    original = suite()
    reversed_suite = ModelEvaluationSuite.create("1.0", tuple(reversed(original.cases)))
    assert original.corpus_digest == reversed_suite.corpus_digest


def test_missing_category_duplicate_case_and_secret_prompt_are_rejected() -> None:
    cases = suite().cases
    replacement = ModelEvaluationCase(
        "planning.replacement",
        EvaluationCategory.PLANNING,
        "Evaluate replacement planning",
        {"safe": True},
    )
    with pytest.raises(ModelEvaluationError, match="every required category"):
        ModelEvaluationSuite.create("1.0", (*cases[:-1], replacement))
    with pytest.raises(ModelEvaluationError, match="unique"):
        ModelEvaluationSuite.create("1.0", (*cases, cases[0]))
    with pytest.raises(ModelEvaluationError, match="secret-like"):
        ModelEvaluationCase(
            "schema.secret",
            EvaluationCategory.SCHEMA_CONFORMANCE,
            "Bearer abcdefghijklmnop",
            {"safe": True},
        )


def test_evidence_binding_requires_unique_external_uuid_per_category() -> None:
    report = execute(suite(), [json.dumps({"safe": True})] * 7)
    evidence = {
        category: UUID(f"30000000-0000-4000-8000-{index:012d}")
        for index, category in enumerate(EvaluationCategory, start=1)
    }
    bound = report.bind_evidence(evidence)
    assert {item.category for item in bound} == set(EvaluationCategory)
    with pytest.raises(ModelEvaluationError, match="one evidence UUID"):
        report.bind_evidence({EvaluationCategory.SCHEMA_CONFORMANCE: next(iter(evidence.values()))})
