from nexus_os.modes import DATA_ANALYSIS_VERSION, DataAnalysisMode


def test_data_analysis_mode_contract_is_versioned_and_callable() -> None:
    assert DATA_ANALYSIS_VERSION == "1.0"
    assert callable(DataAnalysisMode.compile)
