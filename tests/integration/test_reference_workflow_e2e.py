import json

from nexus_os.reference_workflow import ROW_COUNT, ReferenceWorkflow


def test_rw_100k_executes_saves_reopens_and_reports(tmp_path) -> None:
    workspace = tmp_path / "rw"
    first = ReferenceWorkflow(workspace).run()
    reopened = ReferenceWorkflow(workspace).reopen()

    assert first == reopened
    assert first.row_count == ROW_COUNT
    assert first.evidence_count == 7
    assert first.benchmark["browser_render_claim"] is False
    report = json.loads((workspace / "evidence-report.json").read_text())
    assert report["outcome"] == "PASS"
    assert "NOT CLAIMED" in (workspace / "evidence-report.md").read_text()
