from pathlib import Path

from nexus_os.config import load_project_config
from nexus_os.modes import ResearchMode


def test_research_graph_excludes_secrets_and_cannot_publish(tmp_path: Path) -> None:
    path = tmp_path / "research.yaml"
    path.write_text(
        """schema_version: '1.0'
project_id: secure_research
name: Secure Research
mode: research
goal: Research without leaking secrets.
workspace: {root: ./workspace, read_only: false}
providers:
  researcher: {adapter: mock, credential: env:SECRET_CANARY}
secrets: {token: vault:SECRET_CANARY}
policy:
  max_attempts: 2
  max_elapsed_seconds: 3600
  max_cost_usd: 0
  require_approval: [SENSITIVE, DESTRUCTIVE]
acceptance:
  - {id: SECURE_RESEARCH, description: Research stays secure., verifier: nexus.verify.safe}
"""
    )
    graph = ResearchMode().compile(load_project_config(path)).graph
    serialized = str(graph.canonical_dict())

    assert "SECRET_CANARY" not in serialized
    assert "credential" not in serialized
    assert "providers" not in serialized
    assert "external_publication': False" in serialized
    assert all("publish" not in task.kind for task in graph.tasks)
