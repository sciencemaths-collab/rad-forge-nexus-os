import json
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker

from nexus_os.model_qualification import ModelQualificationState, qualify_model
from tests.unit.test_model_evaluation import NOW, execute, suite


def test_controlled_report_can_feed_qualification_only_after_evidence_binding() -> None:
    report = execute(suite(), [json.dumps({"safe": True})] * 7)
    evidence = {
        category: UUID(f"30000000-0000-4000-8000-{index:012d}")
        for index, category in enumerate(report.category_results, start=1)
    }
    qualification = qualify_model(
        qualification_id=UUID("30000000-0000-4000-8000-000000000100"),
        provider_id="local_openai",
        model_id="fixture",
        adapter_version="1.0.0",
        evaluated_at=NOW,
        validity_seconds=3600,
        evaluations=report.bind_evidence(evidence),
    )
    assert qualification.state is ModelQualificationState.QUALIFIED


def test_controlled_report_satisfies_public_schema() -> None:
    report = execute(suite(), [json.dumps({"safe": True})] * 7)
    schema = json.loads(Path("schemas/model-evaluation-report.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(report.canonical())
