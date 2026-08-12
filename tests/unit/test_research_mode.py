from pathlib import Path

import pytest

from nexus_os.config import load_project_config
from nexus_os.modes import ModeCompileError, ResearchMode


def _config(tmp_path: Path, *, mode: str = "research", read_only: bool = False):
    path = tmp_path / "research.yaml"
    path.write_text(
        f"""schema_version: '1.0'
project_id: research_demo
name: Research Demo
mode: {mode}
goal: Determine whether the evidence supports the stated hypothesis.
workspace:
  root: ./workspace
  read_only: {str(read_only).lower()}
  network_allowlist: [example.org]
providers:
  researcher: {{adapter: mock, credential: env:SECRET_CANARY}}
secrets: {{token: vault:SECRET_CANARY}}
policy:
  max_attempts: 3
  max_elapsed_seconds: 7200
  max_cost_usd: 0
  require_approval: [SENSITIVE, DESTRUCTIVE]
acceptance:
  - id: RESEARCH_GROUNDED
    description: Every factual claim is grounded.
    verifier: nexus.verify.claims
"""
    )
    return load_project_config(path)


def test_research_compiles_provenance_first_sequence(tmp_path: Path) -> None:
    result = ResearchMode().compile(_config(tmp_path))
    assert tuple(str(item) for item in result.topological_order) == (
        "protocol",
        "source_acquisition",
        "source_extraction",
        "claim_construction",
        "deterministic_compute",
        "synthesis",
        "conflict_review",
        "citation_verification",
        "reproducibility",
        "evidence_report",
    )
    by_id = {str(task.task_id): task for task in result.graph.tasks}
    assert by_id["source_acquisition"].input["required_source_fields"]
    assert by_id["deterministic_compute"].max_attempts == 1
    assert by_id["synthesis"].input["external_publication"] is False
    assert by_id["conflict_review"].input["retain_contradictions"] is True
    assert by_id["evidence_report"].acceptance_ids == ("RESEARCH_GROUNDED",)


def test_research_graph_is_deterministic(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first, second = ResearchMode().compile(config).graph, ResearchMode().compile(config).graph
    assert first.graph_id == second.graph_id
    assert first.digest == second.digest


@pytest.mark.parametrize(
    ("mode", "read_only", "message"),
    [("app_build", False, "mode"), ("research", True, "writable")],
)
def test_research_rejects_wrong_mode_and_read_only_workspace(
    tmp_path: Path,
    mode: str,
    read_only: bool,
    message: str,
) -> None:
    with pytest.raises(ModeCompileError, match=message):
        ResearchMode().compile(_config(tmp_path, mode=mode, read_only=read_only))
