from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from nexus_os.model_qualification import (
    EvaluationCategory,
    EvaluationResult,
    ModelEvaluation,
    ModelQualificationError,
    ModelQualificationState,
    ModelUse,
    qualify_model,
)

NOW = datetime(2026, 8, 13, 12, tzinfo=UTC)


def evaluations(result: EvaluationResult = EvaluationResult.PASS) -> tuple[ModelEvaluation, ...]:
    return tuple(
        ModelEvaluation(
            f"{category.value}.v1",
            category,
            result,
            (UUID(f"20000000-0000-4000-8000-{index:012d}"),),
            () if result is EvaluationResult.PASS else ("observed failure",),
        )
        for index, category in enumerate(EvaluationCategory, start=1)
    )


def qualify(items: tuple[ModelEvaluation, ...]):
    return qualify_model(
        qualification_id=UUID("20000000-0000-4000-8000-000000000100"),
        provider_id="local_openai",
        model_id="reference-model",
        adapter_version="1.0.0",
        evaluated_at=NOW,
        validity_seconds=3600,
        evaluations=items,
    )


def test_all_passing_categories_qualify_every_declared_use() -> None:
    result = qualify(evaluations())
    assert result.state is ModelQualificationState.QUALIFIED
    assert result.allowed_uses == tuple(ModelUse)
    assert len(result.evidence_digest) == 64
    assert result.to_dict()["evidence_digest"] == result.evidence_digest


def test_limited_tool_selection_does_not_count_as_pass() -> None:
    items = list(evaluations())
    index = list(EvaluationCategory).index(EvaluationCategory.TOOL_SELECTION)
    items[index] = replace(
        items[index], result=EvaluationResult.LIMITED, limitations=("read-only accuracy",)
    )
    result = qualify(tuple(items))
    assert result.state is ModelQualificationState.LIMITED
    assert ModelUse.TOOL_SELECTION not in result.allowed_uses
    assert ModelUse.SENSITIVE_ACTION_PROPOSAL not in result.allowed_uses
    assert ModelUse.CANDIDATE_SPECIFICATION in result.allowed_uses


def test_missing_duplicate_and_cross_category_evidence_are_rejected() -> None:
    items = evaluations()
    with pytest.raises(ModelQualificationError, match="exactly one"):
        qualify(items[:-1])
    with pytest.raises(ModelQualificationError, match="exactly one"):
        qualify((*items, items[0]))
    duplicate_evidence = replace(items[1], evidence_ids=items[0].evidence_ids)
    with pytest.raises(ModelQualificationError, match="unique across"):
        qualify((items[0], duplicate_evidence, *items[2:]))


def test_non_passing_result_requires_a_specific_limitation() -> None:
    with pytest.raises(ModelQualificationError, match="requires a limitation"):
        ModelEvaluation(
            "schema.v1",
            EvaluationCategory.SCHEMA_CONFORMANCE,
            EvaluationResult.FAIL,
            (UUID("20000000-0000-4000-8000-000000000001"),),
        )


def test_expiry_is_fail_closed_at_the_boundary() -> None:
    result = qualify(evaluations())
    assert result.permits(ModelUse.TASK_PLANNING, at=NOW + timedelta(seconds=3599))
    assert not result.permits(ModelUse.TASK_PLANNING, at=NOW + timedelta(seconds=3600))
    assert (
        result.effective_state(at=NOW + timedelta(seconds=3600)) is ModelQualificationState.EXPIRED
    )


def test_digest_is_canonical_across_input_order() -> None:
    forward = qualify(evaluations())
    backward = qualify(tuple(reversed(evaluations())))
    assert forward.evidence_digest == backward.evidence_digest
    assert forward.evaluations == backward.evaluations


@pytest.mark.parametrize("validity", [0, True, 7_776_001])
def test_invalid_validity_is_rejected(validity: int) -> None:
    with pytest.raises(ModelQualificationError, match="validity_seconds"):
        qualify_model(
            qualification_id=UUID("20000000-0000-4000-8000-000000000100"),
            provider_id="local_openai",
            model_id="reference-model",
            adapter_version="1.0.0",
            evaluated_at=NOW,
            validity_seconds=validity,
            evaluations=evaluations(),
        )
