from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from nexus_os.domain import RunId, TraceId
from nexus_os.evidence import GENESIS, EvidenceKind, EvidenceOutcome, EvidenceRecord
from nexus_os.local_model_cli import _manifest
from nexus_os.model_attestation import attest_and_qualify
from nexus_os.model_evaluation import load_benchmark_suite
from nexus_os.model_qualification import ModelQualificationState, ModelUse
from tests.unit.test_model_evaluation import execute
from tests.unit.test_model_evaluation_corpus import ANCHOR, CORPUS

RUN_ID = RunId.parse("40000000-0000-4000-8000-000000000001")
TRACE_ID = TraceId("4" * 32)
EVALUATED_AT = datetime(2026, 8, 13, 16, tzinfo=UTC)
ATTESTED_AT = datetime(2026, 8, 13, 17, tzinfo=UTC)


def manifest(*, fail_category: str | None = None):
    suite = load_benchmark_suite(CORPUS, expected_digest=ANCHOR.read_text().strip())
    outputs = []
    for case in suite.cases:
        expected = dict(case.expected_output)
        if case.category.value == fail_category:
            expected = {"incorrect": True}
        import json

        outputs.append(json.dumps(expected))
    report = execute(suite, outputs)
    return _manifest(
        run_id=RUN_ID,
        trace_id=TRACE_ID,
        model_id="reference-model",
        base_url="http://127.0.0.1:11434/v1",
        report=report.canonical(),
    )


def records(document, *, producer: str = "independent-evaluator"):
    previous = GENESIS
    items = []
    for index, (category, result) in enumerate(
        document["report"]["category_results"].items(), start=1
    ):
        item = EvidenceRecord(
            UUID(f"50000000-0000-4000-8000-{index:012d}"),
            index,
            EVALUATED_AT + timedelta(minutes=index),
            "model-qualification",
            RUN_ID,
            None,
            "independent-reviewer",
            producer,
            EvidenceKind.BENCHMARK,
            EvidenceOutcome.PASS,
            f"model-evaluation:{category}:{result}",
            document["manifest_digest"],
            document["report"]["report_digest"],
            TRACE_ID,
            previous,
        ).seal()
        items.append(item)
        previous = item.record_hash
    return tuple(items)


def qualify(document, evidence):
    return attest_and_qualify(
        document,
        evidence,
        expected_count=7,
        expected_head=evidence[-1].record_hash,
        trusted_producers=frozenset({"independent-evaluator"}),
        qualification_id=UUID("50000000-0000-4000-8000-000000000100"),
        attested_at=ATTESTED_AT,
        validity_seconds=3600,
    )


def test_complete_independent_evidence_promotes_passing_manifest() -> None:
    document = manifest()
    evidence = records(document)
    result = qualify(document, evidence)
    assert result.qualification.state is ModelQualificationState.QUALIFIED
    assert result.qualification.allowed_uses == tuple(ModelUse)
    assert result.evidence_count == 7
    assert result.evidence_head == evidence[-1].record_hash
    assert result.attestor_producers == ("independent-evaluator",)
    assert result.attestation_digest.startswith("sha256:")


def test_attested_failure_remains_limited_instead_of_becoming_a_pass() -> None:
    document = manifest(fail_category="tool_selection")
    result = qualify(document, records(document))
    assert result.qualification.state is ModelQualificationState.LIMITED
    assert ModelUse.TOOL_SELECTION not in result.qualification.allowed_uses
    assert ModelUse.SENSITIVE_ACTION_PROPOSAL not in result.qualification.allowed_uses


def test_attestation_is_deterministic_for_same_anchors() -> None:
    document = manifest()
    evidence = records(document)
    assert qualify(document, evidence).to_dict() == qualify(document, evidence).to_dict()


def test_evidence_helpers_produce_a_valid_sealed_chain() -> None:
    document = manifest()
    evidence = records(document)
    assert evidence[0].previous_record_hash == GENESIS
    assert all(item.record_hash == item.computed_hash() for item in evidence)
    assert (
        replace(evidence[-1], output_digest="sha256:" + "0" * 64).computed_hash()
        != evidence[-1].record_hash
    )
