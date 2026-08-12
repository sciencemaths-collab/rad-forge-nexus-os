from pathlib import Path

from nexus_os.config import load_project_config
from nexus_os.modes import DataAnalysisMode


def test_analysis_graph_excludes_secrets_and_forbids_model_numbers(tmp_path: Path) -> None:
    path = tmp_path / "analysis.yaml"
    path.write_text(
        """schema_version: '1.0'
project_id: secure_analysis
name: Secure Analysis
mode: data_analysis
goal: Analyze without leaking secrets or inventing numbers.
workspace: {root: ./workspace, read_only: false}
providers:
  explainer: {adapter: mock, credential: env:SECRET_CANARY}
secrets: {token: vault:SECRET_CANARY}
policy:
  max_attempts: 2
  max_elapsed_seconds: 3600
  max_cost_usd: 0
  require_approval: [SENSITIVE, DESTRUCTIVE]
acceptance:
  - {id: SAFE_ANALYSIS, description: Analysis is safe., verifier: nexus.verify.safe}
"""
    )
    graph = DataAnalysisMode().compile(load_project_config(path)).graph
    serialized = str(graph.canonical_dict())

    assert "SECRET_CANARY" not in serialized
    assert "credential" not in serialized
    assert "providers" not in serialized
    assert "model_generated_numbers_allowed': False" in serialized
    assert "unverified_numbers_allowed': False" in serialized
