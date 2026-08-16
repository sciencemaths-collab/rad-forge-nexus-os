import json

import pytest

from nexus_os.config_migration import MigrationError, migrate


def test_current_config_is_materialized_canonically_and_privately(tmp_path) -> None:
    source = tmp_path / "source.yaml"
    source.write_text(
        """schema_version: "1.0"
project_id: demo_project
name: Demo
mode: app_build
goal: Build a verified demonstration.
workspace: {root: ./workspace}
providers: {planner: {adapter: mock}}
policy:
  max_attempts: 3
  max_elapsed_seconds: 60
  max_cost_usd: 0
  require_approval: [SENSITIVE, DESTRUCTIVE]
acceptance:
  - {id: DEMO_OK, description: Verification passes., verifier: rad.verify}
""",
        encoding="utf-8",
    )
    target = tmp_path / "migrated" / "project.json"

    migrate(source, target, "1.0", "1.0")

    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["schema_version"] == "1.0"
    assert document["workspace"]["network_allowlist"] == []
    assert not target.stat().st_mode & 0o077


def test_migration_rejects_unknown_path_and_existing_target(tmp_path) -> None:
    source = tmp_path / "project.json"
    source.write_text("{}", encoding="utf-8")
    with pytest.raises(MigrationError, match="unsupported"):
        migrate(source, tmp_path / "output.json", "0.9", "1.0")

    source.write_text(
        '{"schema_version":"1.0","project_id":"abc","name":"A","mode":"app_build",'
        '"goal":"A goal","workspace":{"root":"."},"providers":{"p":{"adapter":"mock"}},'
        '"policy":{"max_attempts":1,"max_elapsed_seconds":1,"max_cost_usd":0,'
        '"require_approval":[]},"acceptance":[{"id":"ABC","description":"ok",'
        '"verifier":"rad.verify"}]}',
        encoding="utf-8",
    )
    target = tmp_path / "output.json"
    target.write_text("preserve", encoding="utf-8")
    with pytest.raises(MigrationError, match="new writable file"):
        migrate(source, target, "1.0", "1.0")
    assert target.read_text(encoding="utf-8") == "preserve"
