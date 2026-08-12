from nexus_os.modes import RESEARCH_VERSION, ResearchMode


def test_research_mode_contract_is_versioned_and_callable() -> None:
    assert RESEARCH_VERSION == "1.0"
    assert callable(ResearchMode.compile)
