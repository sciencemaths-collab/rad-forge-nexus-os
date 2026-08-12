from pathlib import Path

from nexus_os.config import load_project_config
from nexus_os.graph import compile_task_graph, validate_task_graph
from nexus_os.modes import DataAnalysisMode


def test_analysis_graph_round_trips_frozen_contract() -> None:
    path = Path("examples/project.data-analysis.yaml")
    graph = DataAnalysisMode().compile(load_project_config(path)).graph
    round_tripped = validate_task_graph(compile_task_graph(graph.canonical_dict())).graph

    assert round_tripped.digest == graph.digest
    reopen = next(task for task in round_tripped.tasks if str(task.task_id) == "reopen_verify")
    assert tuple(reopen.input["deterministic_checks"]) == (
        "dataset_digest_matches",
        "artifacts_match",
        "state_is_compatible",
    )
