from pathlib import Path

import pytest

from nexus_os.config import load_project_config
from nexus_os.modes import DataAnalysisMode, ModeCompileError


def _config(tmp_path: Path, *, mode: str = "data_analysis", read_only: bool = False):
    path = tmp_path / "analysis.yaml"
    path.write_text(
        f"""schema_version: '1.0'
project_id: analysis_demo
name: Analysis Demo
mode: {mode}
goal: Analyze a dataset with traceable calculations.
workspace:
  root: ./workspace
  read_only: {str(read_only).lower()}
providers:
  explainer: {{adapter: mock, credential: env:SECRET_CANARY}}
secrets: {{token: vault:SECRET_CANARY}}
policy:
  max_attempts: 3
  max_elapsed_seconds: 7200
  max_cost_usd: 0
  require_approval: [SENSITIVE, DESTRUCTIVE]
acceptance:
  - id: ANALYSIS_GROUNDED
    description: Numeric claims trace to computed artifacts.
    verifier: nexus.verify.numeric_claims
"""
    )
    return load_project_config(path)


def test_analysis_compiles_deterministic_grounded_sequence(tmp_path: Path) -> None:
    result = DataAnalysisMode().compile(_config(tmp_path))
    assert tuple(str(item) for item in result.topological_order) == (
        "ingestion", "schema_inspection", "quality_check", "statistics", "chart_spec",
        "explanation", "persistence", "reopen_verify", "evidence_report",
    )
    by_id = {str(task.task_id): task for task in result.graph.tasks}
    assert by_id["ingestion"].input["model_generated_numbers_allowed"] is False
    assert by_id["statistics"].max_attempts == 1
    assert by_id["explanation"].max_attempts == 3
    assert by_id["explanation"].input["unverified_numbers_allowed"] is False
    assert by_id["evidence_report"].acceptance_ids == ("ANALYSIS_GROUNDED",)


def test_analysis_graph_is_deterministic(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = DataAnalysisMode().compile(config).graph
    second = DataAnalysisMode().compile(config).graph
    assert first.graph_id == second.graph_id
    assert first.digest == second.digest


@pytest.mark.parametrize(
    ("mode", "read_only", "message"),
    [("research", False, "mode"), ("data_analysis", True, "writable")],
)
def test_analysis_rejects_wrong_mode_and_read_only_workspace(
    tmp_path: Path, mode: str, read_only: bool, message: str,
) -> None:
    with pytest.raises(ModeCompileError, match=message):
        DataAnalysisMode().compile(_config(tmp_path, mode=mode, read_only=read_only))
