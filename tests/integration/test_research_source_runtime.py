import asyncio
import json
from datetime import timedelta

from nexus_os.agent_api import AgentApiRequest, AgentIdentity
from nexus_os.agent_store import AgentSessionStore, candidate_digest
from nexus_os.local_agent_application import RandomIds, _create_reference_runtime
from tests.contract.test_agent_handoff_contract import NOW, SESSION, TRACE, _approved, _document


def _research_document() -> dict:
    document = _document(capabilities=("research.planning",))
    document.update(
        objective="Evaluate a protein-interaction hypothesis from local literature.",
        mode="research",
        required_capabilities=["research.planning"],
    )
    unsigned = {key: value for key, value in document.items() if key != "candidate_digest"}
    return {**unsigned, "candidate_digest": candidate_digest(unsigned)}


def test_research_source_stage_executes_real_ingestion_with_evidence(tmp_path) -> None:
    sessions = AgentSessionStore(tmp_path / "agent.sqlite")
    _approved(sessions, _research_document())
    workspace = tmp_path / "workspace"
    sources = workspace / "research-sources"
    sources.mkdir(parents=True)
    (sources / "study.md").write_text("# Protein interaction\nThe assay reported binding.\n")
    (sources / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "sources": [
                    {
                        "path": "study.md",
                        "locator": "doi:10.0000/protein.example",
                        "retrieved_at": "2026-08-16T00:00:00Z",
                        "license_access": "Operator-supplied local research source",
                    }
                ],
            }
        )
    )
    facade = _create_reference_runtime(tmp_path, sessions, RandomIds())
    identity = AgentIdentity(
        "local-owner",
        frozenset({"agent:execute", "agent:read", "agent:approve"}),
        True,
    )
    started = facade.start(
        SESSION,
        identity,
        AgentApiRequest(
            "POST",
            f"/v1/agent/sessions/{SESSION}/runtime",
            {},
            None,
            "research-start-0001",
            NOW + timedelta(minutes=1),
            TRACE,
        ),
        {"workspace_root": str(workspace)},
    )
    assert started["run_state"] == "READY"

    for number in (2, 3):
        result = asyncio.run(
            facade.tick(
                SESSION,
                identity,
                AgentApiRequest(
                    "POST",
                    f"/v1/agent/sessions/{SESSION}/runtime/ticks",
                    {},
                    None,
                    f"research-tick-{number:04d}",
                    NOW + timedelta(minutes=number),
                    TRACE,
                ),
                None,
            )
        )
        assert result["outcome"] == "SUCCEEDED"

    artifact = json.loads((workspace / ".rad-agent-artifacts/sources.json").read_text())
    assert artifact["tool"] == "research.ingest_local_sources"
    assert artifact["source_count"] == 1
    evidence = facade.evidence(SESSION)
    assert evidence["chain_status"] == "VERIFIED"
    assert evidence["record_count"] == 2
