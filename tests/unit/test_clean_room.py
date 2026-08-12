from scripts.clean_room import independent_review, materialize_snapshot


def test_snapshot_excludes_dirty_and_dependency_directories(tmp_path) -> None:
    source = tmp_path / "source"
    directories = (
        ".github",
        "contracts",
        "docs",
        "examples",
        "schemas",
        "scripts",
        "sdk",
        "src",
        "tests",
    )
    for directory in directories:
        (source / directory).mkdir(parents=True)
        (source / directory / "keep.txt").write_text(directory)
    for name in (".gitignore", "AGENTS.md", "README.md", "pyproject.toml", "uv.lock"):
        (source / name).write_text(name)
    (source / "src/node_modules").mkdir()
    (source / "src/node_modules/drop.txt").write_text("drop")
    destination = tmp_path / "snapshot"

    digest = materialize_snapshot(source, destination)
    assert digest.startswith("sha256:")
    assert not (destination / "src/node_modules").exists()


def test_independent_review_detects_unsafe_source_and_claim_drift(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs/runbooks").mkdir(parents=True)
    (tmp_path / "src/bad.py").write_text("import openai\nvalue = eval('1')\n")
    (tmp_path / "docs/runbooks/STATUS.md").write_text("production ready")
    categories = {item.category for item in independent_review(tmp_path)}
    assert categories == {"dynamic_execution", "vendor_import_in_core", "completion_claim_drift"}
