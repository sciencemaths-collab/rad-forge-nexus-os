import json
from copy import deepcopy
from pathlib import Path

import pytest

from nexus_os.optimization_adapter import (
    OptimizationAdapterError,
    _digest,
    attest_pathwoven_qualification,
)

QUALIFICATION = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "pathwoven-qualification-0.2.0.json").read_text()
)


def test_tampered_pathwoven_qualification_report_is_rejected() -> None:
    tampered = deepcopy(QUALIFICATION)
    tampered["cases"][0]["best_value"] = 999
    with pytest.raises(OptimizationAdapterError, match="not trusted"):
        attest_pathwoven_qualification(tampered)


def test_self_signed_unqualified_pathwoven_report_is_rejected() -> None:
    unqualified = deepcopy(QUALIFICATION)
    unqualified["qualification"] = "UNQUALIFIED"
    unqualified["report_digest"] = _digest(
        {key: value for key, value in unqualified.items() if key != "report_digest"}
    )
    with pytest.raises(OptimizationAdapterError, match="not trusted"):
        attest_pathwoven_qualification(unqualified)
