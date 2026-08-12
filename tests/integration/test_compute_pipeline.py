from nexus_os.compute import DeterministicCompute


def test_csv_to_schema_statistics_and_chart_pipeline() -> None:
    engine = DeterministicCompute()
    loaded = engine.load_csv(b"day,total\nMon,10\nTue,15\n")
    schema = engine.inspect_schema(loaded.value)
    summary = engine.summarize(loaded.value, ["total"])
    chart = engine.chart_inputs(loaded.value, kind="line", x="day", y="total")

    assert schema.value["row_count"] == 2
    assert summary.value["total"]["mean"] == 12.5
    assert tuple(dict(item) for item in chart.value["data"]) == (
        {"day": "Mon", "total": 10},
        {"day": "Tue", "total": 15},
    )
    assert len({item.provenance.output_digest for item in (schema, summary, chart)}) == 3
