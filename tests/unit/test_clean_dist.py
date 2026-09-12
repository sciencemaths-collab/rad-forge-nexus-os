from pathlib import Path

import pytest

from scripts.clean_dist import clean


def test_clean_removes_only_generated_rad_distributions(tmp_path: Path) -> None:
    destination = tmp_path / "dist"
    destination.mkdir()
    stale_wheel = destination / "nexus_os-0.1-py3-none-any.whl"
    stale_source = destination / "nexus_os-0.1.tar.gz"
    unrelated = destination / "another_package-1.0.whl"
    marker = destination / ".gitignore"
    for path in (stale_wheel, stale_source, unrelated, marker):
        path.write_bytes(b"generated")

    removed = clean(tmp_path)

    assert removed == (stale_wheel, stale_source)
    assert unrelated.is_file()
    assert marker.is_file()


def test_clean_rejects_matching_symlink(tmp_path: Path) -> None:
    destination = tmp_path / "dist"
    destination.mkdir()
    outside = tmp_path / "outside.whl"
    outside.write_bytes(b"preserve")
    (destination / "nexus_os-unsafe.whl").symlink_to(outside)

    with pytest.raises(RuntimeError, match="unsafe"):
        clean(tmp_path)
    assert outside.read_bytes() == b"preserve"
