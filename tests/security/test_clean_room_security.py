from pathlib import Path

from scripts.clean_room import independent_review


def test_current_repository_passes_independent_static_review() -> None:
    assert independent_review(Path.cwd()) == ()
