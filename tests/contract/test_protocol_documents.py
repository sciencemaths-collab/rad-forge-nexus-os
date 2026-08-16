from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def test_openapi_has_required_control_operations_and_local_refs() -> None:
    document = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    assert document["openapi"] == "3.1.1"
    operations = {
        operation["operationId"]
        for path in document["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    required = {
        "createProject",
        "planProject",
        "createRun",
        "cancelRun",
        "resumeRun",
        "listEvidence",
        "decideApproval",
        "listProviders",
        "listCapabilities",
    }
    assert required <= operations
    text = (ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    for schema_name in (
        "project",
        "evidence",
        "approval",
        "provider",
        "capability",
        "agent-session",
        "agent-candidate-specification",
        "model-qualification",
    ):
        if f"../schemas/{schema_name}.schema.json" in text:
            assert (ROOT / f"schemas/{schema_name}.schema.json").exists()


def test_agent_api_mutations_require_idempotency_keys() -> None:
    document = yaml.safe_load((ROOT / "contracts/agent-openapi.yaml").read_text(encoding="utf-8"))
    operations = {
        operation["operationId"]
        for methods in document["paths"].values()
        for operation in methods.values()
    }
    assert operations == {
        "createAgentSession",
        "getAgentSession",
        "submitAgentClarification",
        "getAgentCandidateSpecification",
        "reviseAgentCandidateSpecification",
        "approveAgentCandidateSpecification",
        "startAgentRuntime",
        "getAgentRuntime",
        "pauseAgentRuntime",
        "resumeAgentRuntimeExecution",
        "cancelAgentRuntime",
        "previewAgentRuntimeAction",
        "prepareAgentRuntimeTask",
        "listAgentRuntimePreparations",
        "listAgentRuntimeEvidence",
        "listAgentRuntimeArtifacts",
        "downloadAgentRuntimeArtifact",
        "tickAgentRuntime",
        "decideAgentRuntimeApproval",
        "verifyAgentRuntimeCompletion",
        "listModelQualifications",
    }
    for path, operations in document["paths"].items():
        if not path.startswith("/v1/agent/"):
            continue
        for method, operation in operations.items():
            if method != "post":
                continue
            parameters = operation.get("parameters", [])
            assert {"$ref": "#/components/parameters/IdempotencyKey"} in parameters
    text = (ROOT / "contracts/agent-openapi.yaml").read_text(encoding="utf-8")
    for schema_name in (
        "agent-session",
        "agent-candidate-specification",
        "model-qualification",
    ):
        assert f"../schemas/{schema_name}.schema.json" in text
        assert (ROOT / f"schemas/{schema_name}.schema.json").exists()


def test_mcp_tools_have_valid_typed_boundaries_and_effects() -> None:
    document = json.loads((ROOT / "contracts/mcp/tools.json").read_text(encoding="utf-8"))
    names: set[str] = set()
    for tool in document["tools"]:
        assert tool["name"] not in names
        names.add(tool["name"])
        assert tool["effect"] in {"READ_ONLY", "WORKSPACE_WRITE", "SENSITIVE", "DESTRUCTIVE"}
        Draft202012Validator.check_schema(tool["inputSchema"])
        Draft202012Validator.check_schema(tool["outputSchema"])
        if tool["effect"] in {"SENSITIVE", "DESTRUCTIVE"}:
            assert tool["approval_required"] is True
