from scripts.clean_room import COPY_PATHS


def test_clean_room_contract_contains_all_release_inputs() -> None:
    required = {
        "CONTRIBUTING.md",
        "LICENSE",
        "README.md",
        "SECURITY.md",
        "benchmarks",
        "contracts",
        "docs",
        "schemas",
        "scripts",
        "sdk",
        "src",
        "tests",
        "uv.lock",
    }
    assert required <= set(COPY_PATHS)
