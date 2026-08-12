from pathlib import Path

import pytest

from nexus_os.config import load_project_config
from nexus_os.domain import ActionEffect
from nexus_os.modes import AppBuildMode, ModeCompileError


def _config(tmp_path: Path, *, mode: str = "app_build", read_only: bool = False):
    path = tmp_path / "project.yaml"
    path.write_text(
        f"""schema_version: '1.0'
project_id: app_demo
name: Demo App
mode: {mode}
goal: Build a verified demo application.
workspace:
  root: ./workspace
  read_only: {str(read_only).lower()}
providers:
  planner:
    adapter: mock
    credential: env:SECRET_CANARY
secrets:
  token: vault:SECRET_CANARY
policy:
  max_attempts: 3
  max_elapsed_seconds: 3600
  max_cost_usd: 0
  require_approval: [SENSITIVE, DESTRUCTIVE]
acceptance:
  - id: APP_TESTED
    description: All required tests pass.
    verifier: nexus.verify.tests
"""
    )
    return load_project_config(path)


def test_app_build_compiles_required_fail_fast_sequence(tmp_path: Path) -> None:
    result = AppBuildMode().compile(_config(tmp_path))
    ids = tuple(str(item) for item in result.topological_order)

    assert ids == (
        "specification",
        "design",
        "contract_test",
        "implementation",
        "unit_test",
        "integration_test",
        "security_test",
        "failure_test",
        "evidence_report",
    )
    assert all(task.effect is ActionEffect.WORKSPACE_WRITE for task in result.graph.tasks)
    assert result.graph.tasks[2].max_attempts == 1
    assert result.graph.tasks[3].max_attempts == 3
    assert result.graph.tasks[-1].acceptance_ids == ("APP_TESTED",)


def test_app_build_graph_is_digest_deterministic(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = AppBuildMode().compile(config).graph
    second = AppBuildMode().compile(config).graph
    assert first.graph_id == second.graph_id
    assert first.digest == second.digest


@pytest.mark.parametrize(
    ("mode", "read_only", "message"),
    [("research", False, "mode"), ("app_build", True, "writable")],
)
def test_wrong_mode_and_read_only_workspace_are_rejected(
    tmp_path: Path,
    mode: str,
    read_only: bool,
    message: str,
) -> None:
    with pytest.raises(ModeCompileError, match=message):
        AppBuildMode().compile(_config(tmp_path, mode=mode, read_only=read_only))
