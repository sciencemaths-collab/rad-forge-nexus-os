from pathlib import Path

from nexus_os.config import load_project_config
from nexus_os.modes import AppBuildMode


def test_mode_graph_does_not_copy_provider_or_secret_references(tmp_path: Path) -> None:
    path = tmp_path / "project.yaml"
    path.write_text(
        """schema_version: '1.0'
project_id: secure_app
name: Secure App
mode: app_build
goal: Build without leaking configuration secrets.
workspace: {root: ./workspace, read_only: false}
providers:
  planner: {adapter: mock, credential: env:SECRET_CANARY}
secrets: {token: vault:SECRET_CANARY}
policy:
  max_attempts: 2
  max_elapsed_seconds: 1000
  max_cost_usd: 0
  require_approval: [SENSITIVE, DESTRUCTIVE]
acceptance:
  - {id: SAFE_BUILD, description: Build is safe., verifier: nexus.verify.safe}
"""
    )
    graph = AppBuildMode().compile(load_project_config(path)).graph

    serialized = str(graph.canonical_dict())
    assert "SECRET_CANARY" not in serialized
    assert "credential" not in serialized
    assert "providers" not in serialized
