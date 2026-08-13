from pathlib import Path

from nexus_os.evidence import GENESIS, EvidenceLedger
from tests.unit.test_model_attestation import RUN_ID, manifest, qualify, records


def test_persisted_evidence_chain_can_drive_attested_qualification(tmp_path: Path) -> None:
    document = manifest()
    source = records(document)
    ledger = EvidenceLedger(tmp_path / "evidence.sqlite")
    head = GENESIS
    for item in source:
        unsealed = type(item)(
            item.evidence_id,
            item.sequence,
            item.timestamp,
            item.project_id,
            item.run_id,
            item.task_id,
            item.actor,
            item.producer,
            item.kind,
            item.outcome,
            item.test_id,
            item.input_digest,
            item.output_digest,
            item.trace_id,
            item.previous_record_hash,
        )
        head = ledger.append(unsealed, expected_head=head).record_hash
    persisted = ledger.records("model-qualification", RUN_ID)
    result = qualify(document, persisted)
    ledger.close()
    assert result.evidence_head == head
    assert result.evidence_count == 7
