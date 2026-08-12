from pathlib import Path

import yaml

from scripts.release_evidence import GATES, REPORT_VERSION


def test_release_gate_contract_has_required_order_and_version() -> None:
    assert REPORT_VERSION == "1.0"
    assert tuple(gate.gate_id for gate in GATES) == (
        "format",
        "lint",
        "typecheck",
        "schemas",
        "unit",
        "contract",
        "integration",
        "security",
        "provider_conformance",
        "rw_100k",
        "typescript",
        "build",
    )


def test_ci_workflow_is_least_privilege_and_has_dependency_review() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    assert "dependency-review" in workflow["jobs"]
    assert workflow["jobs"]["qualify"]["timeout-minutes"] == 30
