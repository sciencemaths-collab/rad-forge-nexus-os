from pathlib import Path

import yaml

from nexus_os.config import load_project_config
from nexus_os.graph import compile_task_graph, validate_task_graph
from nexus_os.modes import AppBuildMode


def test_mode_output_round_trips_through_frozen_graph_contract(tmp_path: Path) -> None:
    document = {
        "schema_version": "1.0",
        "project_id": "roundtrip_app",
        "name": "Roundtrip",
        "mode": "app_build",
        "goal": "Build a contract-verified application.",
        "workspace": {"root": "./workspace", "read_only": False},
        "providers": {"planner": {"adapter": "mock"}},
        "secrets": {},
        "policy": {
            "max_attempts": 2,
            "max_elapsed_seconds": 3600,
            "max_cost_usd": 0,
            "require_approval": ["SENSITIVE", "DESTRUCTIVE"],
        },
        "acceptance": [
            {
                "id": "ROUNDTRIP_OK",
                "description": "Contract round trip passes.",
                "verifier": "nexus.verify.contract",
            }
        ],
    }
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(document))
    graph = AppBuildMode().compile(load_project_config(path)).graph
    wire = graph.canonical_dict()
    round_tripped = validate_task_graph(compile_task_graph(wire)).graph

    assert round_tripped.digest == graph.digest
    evidence = next(task for task in round_tripped.tasks if str(task.task_id) == "evidence_report")
    assert evidence.acceptance_ids == ("ROUNDTRIP_OK",)
