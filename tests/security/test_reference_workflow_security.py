import json

import pytest

from nexus_os.evidence import EvidenceError
from nexus_os.reference_workflow import ReferenceWorkflow, ReferenceWorkflowError


def test_state_mutation_is_detected_on_reopen(tmp_path) -> None:
    workspace = tmp_path / "rw"
    ReferenceWorkflow(workspace).run()
    path = workspace / "state.json"
    state = json.loads(path.read_text())
    state["row_count"] = 1
    path.write_text(json.dumps(state))

    with pytest.raises(ReferenceWorkflowError, match="digest"):
        ReferenceWorkflow(workspace).reopen()


def test_existing_evidence_cannot_be_silently_replayed(tmp_path) -> None:
    workflow = ReferenceWorkflow(tmp_path / "rw")
    workflow.run()
    with pytest.raises(EvidenceError, match=r"duplicate|head|conflicting"):
        workflow.run()
