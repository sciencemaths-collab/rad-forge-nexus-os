from dataclasses import replace
from uuid import UUID

import pytest

from nexus_os.model_qualification import (
    EvaluationCategory,
    EvaluationResult,
    ModelEvaluation,
    ModelQualificationError,
    ModelUse,
)
from tests.unit.test_model_qualification import evaluations, qualify


def test_failed_approval_and_adversarial_categories_block_privileged_proposals() -> None:
    items = list(evaluations())
    for category in (EvaluationCategory.APPROVAL_BOUNDARY, EvaluationCategory.ADVERSARIAL_INPUT):
        index = list(EvaluationCategory).index(category)
        items[index] = replace(
            items[index], result=EvaluationResult.FAIL, limitations=("unsafe behavior",)
        )
    result = qualify(tuple(items))
    assert ModelUse.TASK_PLANNING not in result.allowed_uses
    assert ModelUse.TOOL_SELECTION not in result.allowed_uses
    assert ModelUse.REPAIR_PROPOSAL not in result.allowed_uses
    assert ModelUse.SENSITIVE_ACTION_PROPOSAL not in result.allowed_uses


def test_schema_failure_grants_no_use_even_when_other_categories_pass() -> None:
    items = list(evaluations())
    items[0] = replace(items[0], result=EvaluationResult.FAIL, limitations=("invalid output",))
    result = qualify(tuple(items))
    assert result.allowed_uses == ()


def test_secret_like_limitation_is_rejected_before_evidence_serialization() -> None:
    with pytest.raises(ModelQualificationError, match="secret-like"):
        ModelEvaluation(
            "schema.v1",
            EvaluationCategory.SCHEMA_CONFORMANCE,
            EvaluationResult.FAIL,
            (UUID("20000000-0000-4000-8000-000000000001"),),
            ("Bearer abcdefghijklmnop",),
        )
