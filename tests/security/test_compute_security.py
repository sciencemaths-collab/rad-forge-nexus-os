import pytest

from nexus_os.compute import ComputeError, DeterministicCompute


def test_bounds_fail_before_unbounded_work() -> None:
    engine = DeterministicCompute()
    with pytest.raises(ComputeError, match="row limit"):
        engine.load_csv(b"a\n1\n2\n", max_rows=1)
    with pytest.raises(ComputeError, match="max_rows"):
        engine.load_csv(b"a\n1\n", max_rows=1_000_001)


def test_unknown_columns_and_non_numeric_chart_fail_closed() -> None:
    engine = DeterministicCompute()
    table = engine.load_csv(b"name,value\na,one\n").value
    with pytest.raises(ComputeError, match="does not exist"):
        engine.summarize(table, ["secret"])
    with pytest.raises(ComputeError, match="numeric"):
        engine.chart_inputs(table, kind="line", x="name", y="value")


def test_error_does_not_echo_hostile_input() -> None:
    canary = "SECRET_CANARY"
    engine = DeterministicCompute()
    table = engine.load_csv(f"name\n{canary}\n".encode()).value
    with pytest.raises(ComputeError) as raised:
        engine.sort(table, canary)
    assert canary not in str(raised.value)


def test_computed_output_cannot_be_mutated_after_digesting() -> None:
    engine = DeterministicCompute()
    result = engine.summarize(engine.load_csv(b"value\n1\n").value)
    with pytest.raises(TypeError):
        result.value["value"]["mean"] = 99
