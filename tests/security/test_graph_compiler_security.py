"""Security and failure tests for untrusted graph compilation."""

import pytest

from nexus_os.graph import MAX_GRAPH_BYTES, GraphCompileError, compile_task_graph


def test_non_json_and_nonfinite_values_are_rejected() -> None:
    with pytest.raises(GraphCompileError, match="canonical JSON"):
        compile_task_graph({"value": object()})
    with pytest.raises(GraphCompileError, match="canonical JSON"):
        compile_task_graph({"value": float("nan")})


def test_oversized_graph_is_rejected_before_schema_work() -> None:
    with pytest.raises(GraphCompileError, match="4 MiB"):
        compile_task_graph({"padding": "x" * (MAX_GRAPH_BYTES + 1)})


def test_error_does_not_echo_untrusted_input() -> None:
    canary = "TOP_SECRET_CANARY"
    with pytest.raises(GraphCompileError) as caught:
        compile_task_graph({"schema_version": canary})
    assert canary not in str(caught.value)
