import hashlib

import pytest

from nexus_os.reference_workflow import ROW_COUNT, ReferenceWorkflowError, generate_fixture


def test_fixture_is_exact_and_deterministic() -> None:
    first, second = generate_fixture(), generate_fixture()
    assert first == second
    assert first.count(b"\n") == ROW_COUNT + 1
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()


def test_fixture_count_cannot_weaken_acceptance() -> None:
    with pytest.raises(ReferenceWorkflowError, match="exactly"):
        generate_fixture(rows=99_999)
