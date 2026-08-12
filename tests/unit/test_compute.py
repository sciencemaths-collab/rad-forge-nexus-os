import pytest

from nexus_os.compute import ComputeError, DeterministicCompute, Table

CSV = b"category,value,active\na,2,true\nb,4,false\na,,true\n"


def test_load_schema_and_provenance_are_deterministic() -> None:
    engine = DeterministicCompute()
    first = engine.load_csv(CSV)
    second = engine.load_csv(CSV)

    assert isinstance(first.value, Table)
    assert first.value.types == ("string", "integer", "boolean")
    assert first.value.row_count == 3
    assert first.provenance == second.provenance
    assert engine.inspect_schema(first.value).value["columns"][1] == {
        "name": "value",
        "type": "integer",
        "nullable": True,
    }


def test_summary_uses_deterministic_numbers() -> None:
    engine = DeterministicCompute()
    table = engine.load_csv(CSV).value
    result = engine.summarize(table, ["value"]).value["value"]

    assert result == {
        "count": 2,
        "null_count": 1,
        "distinct_count": 2,
        "min": 2.0,
        "max": 4.0,
        "mean": 3.0,
        "median": 3.0,
    }


def test_select_sort_and_chart_inputs() -> None:
    engine = DeterministicCompute()
    table = engine.load_csv(CSV).value
    selected = engine.select(table, ["category", "value"]).value
    sorted_table = engine.sort(selected, "value", descending=True).value
    chart = engine.chart_inputs(sorted_table, kind="bar", x="category", y="value")

    assert sorted_table.rows == (("b", 4), ("a", 2), ("a", None))
    assert chart.value["data"][0] == {"category": "b", "value": 4}
    assert chart.provenance.input_digest == sorted_table.digest


@pytest.mark.parametrize(
    "payload",
    [b"a,a\n1,2\n", b"a,b\n1\n", b"a\n\xff\n", b""],
)
def test_bad_csv_is_rejected(payload: bytes) -> None:
    with pytest.raises(ComputeError):
        DeterministicCompute().load_csv(payload)
