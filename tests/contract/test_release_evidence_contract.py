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
        "python_dependency_audit",
        "typescript_dependency_audit",
        "unit",
        "contract",
        "integration",
        "security",
        "build",
        "clean_wheel",
        "browser_acceptance",
        "provider_conformance",
        "rw_100k",
        "typescript",
        "qualified_browser",
    )


def test_ci_workflow_is_least_privilege_and_uses_portable_audits() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"qualify"}
    assert workflow["jobs"]["qualify"]["timeout-minutes"] == 30
