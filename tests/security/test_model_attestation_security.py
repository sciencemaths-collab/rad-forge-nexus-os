from dataclasses import replace
from datetime import timedelta

import pytest

from nexus_os.evidence import EvidenceKind, EvidenceOutcome
from nexus_os.model_attestation import ModelAttestationError, attest_and_qualify
from tests.unit.test_model_attestation import ATTESTED_AT, manifest, qualify, records


def test_manifest_and_report_digest_tampering_are_rejected() -> None:
    document = manifest()
    tampered = {**document, "model_id": "different-model"}
    with pytest.raises(ModelAttestationError, match="manifest digest mismatch"):
        qualify(tampered, records(document))

    tampered_report = {**document, "report": {**document["report"], "suite_version": "other"}}
    with pytest.raises(ModelAttestationError, match="manifest digest mismatch"):
        qualify(tampered_report, records(document))


@pytest.mark.parametrize(
    "change",
    [
        {"producer": "untrusted-evaluator"},
        {"kind": EvidenceKind.QUALIFICATION},
        {"outcome": EvidenceOutcome.FAIL},
        {"input_digest": "sha256:" + "0" * 64},
        {"output_digest": "sha256:" + "0" * 64},
        {"test_id": "model-evaluation:planning:PASS"},
        {"timestamp": ATTESTED_AT + timedelta(seconds=1)},
    ],
)
def test_mismatched_untrusted_or_future_category_evidence_is_rejected(change) -> None:  # type: ignore[no-untyped-def]
    document = manifest()
    evidence = list(records(document))
    evidence[0] = (
        replace(evidence[0], **change).seal()
        if not evidence[0].record_hash
        else replace(evidence[0], record_hash="", **change).seal()
    )
    with pytest.raises(ModelAttestationError):
        qualify(document, tuple(evidence))


def test_missing_record_wrong_head_and_empty_trust_anchor_fail_closed() -> None:
    document = manifest()
    evidence = records(document)
    with pytest.raises(ModelAttestationError, match="exactly seven"):
        qualify(document, evidence[:-1])
    with pytest.raises(ModelAttestationError, match="integrity"):
        attest_and_qualify(
            document,
            evidence,
            expected_count=7,
            expected_head="sha256:" + "0" * 64,
            trusted_producers=frozenset({"independent-evaluator"}),
            qualification_id=__import__("uuid").UUID("50000000-0000-4000-8000-000000000100"),
            attested_at=ATTESTED_AT,
            validity_seconds=3600,
        )
    with pytest.raises(ModelAttestationError, match="allowlist"):
        attest_and_qualify(
            document,
            evidence,
            expected_count=7,
            expected_head=evidence[-1].record_hash,
            trusted_producers=frozenset(),
            qualification_id=__import__("uuid").UUID("50000000-0000-4000-8000-000000000100"),
            attested_at=ATTESTED_AT,
            validity_seconds=3600,
        )
