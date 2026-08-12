from pathlib import Path

from nexus_os.config import load_project_config
from nexus_os.graph import compile_task_graph, validate_task_graph
from nexus_os.modes import ResearchMode


def test_research_graph_round_trips_frozen_contract(tmp_path: Path) -> None:
    path = Path("examples/project.research.yaml")
    graph = ResearchMode().compile(load_project_config(path)).graph
    round_tripped = validate_task_graph(compile_task_graph(graph.canonical_dict())).graph

    assert round_tripped.digest == graph.digest
    citation = next(
        task for task in round_tripped.tasks if str(task.task_id) == "citation_verification"
    )
    assert tuple(citation.input["deterministic_checks"]) == (
        "citation_exists",
        "source_span_exists",
        "artifact_value_matches",
    )
