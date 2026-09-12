import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest

from nexus_os.optimization_adapter import (
    OptimizationAdapterError,
    PathWovenAdapter,
    _digest,
)

QUALIFICATION = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "pathwoven-qualification-0.2.0.json").read_text()
)


def adapter(call):
    return PathWovenAdapter(call, QUALIFICATION)


def request():
    return {"objective": "sphere", "dimensions": 2, "max_evaluations": 160, "seed": 7}


def result(value):
    normalized = {**value, "sectors": 8, "particles_per_sector": 4}
    return {
        "schema_version": "1.0",
        "engine_id": "pathwoven-dcgo",
        "engine_version": "0.2.0",
        "adapter_version": "1.0.0",
        "capability_id": "rad.optimization.pathwoven",
        "request_digest": _digest(normalized),
        "objective": "sphere",
        "best_x": [0.1, 0.2],
        "best_value": 0.05,
        "evaluations": 160,
        "iterations": 4,
        "seed": 7,
        "convergence": [1.0, 0.5, 0.2, 0.05],
        "limitations": ["stochastic_no_global_optimum_guarantee"],
    }


def test_adapter_manifest_and_validated_execution() -> None:
    bound = adapter(lambda value: result(value))
    assert bound.manifest().capability_id == "rad.optimization.pathwoven"
    assert bound.manifest().qualification_required is True
    output = asyncio.run(bound.execute("optimization.solve", request()))
    assert output["best_value"] == 0.05


@pytest.mark.parametrize(
    "field", ["engine_version", "request_digest", "evaluations", "best_x", "convergence"]
)
def test_adapter_rejects_tampered_or_malformed_results(field) -> None:
    def broken(value):
        output = deepcopy(result(value))
        output[field] = {
            "engine_version": "9.0.0",
            "request_digest": "sha256:" + "0" * 64,
            "evaluations": 161,
            "best_x": [0.1],
            "convergence": [0.1, 0.2, 0.3, 0.4],
        }[field]
        return output

    with pytest.raises(OptimizationAdapterError):
        asyncio.run(adapter(broken).execute("optimization.solve", request()))


def test_adapter_rejects_code_like_objectives_and_safe_wraps_engine_errors() -> None:
    bound = adapter(lambda value: (_ for _ in ()).throw(RuntimeError("secret")))
    with pytest.raises(OptimizationAdapterError, match="unsupported"):
        asyncio.run(bound.execute("optimization.solve", {**request(), "objective": "python:exec"}))
    with pytest.raises(OptimizationAdapterError, match="execution failed") as captured:
        asyncio.run(bound.execute("optimization.solve", request()))
    assert "secret" not in str(captured.value)
