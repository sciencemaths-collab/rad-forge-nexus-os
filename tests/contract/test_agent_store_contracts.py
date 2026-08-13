from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from nexus_os.agent_store import AgentSessionStore, CandidateSpecification
from scripts.validate_contracts import ROOT, load
from tests.unit.test_agent_store import AT, candidate, created, uid


def validator(name: str):
    schema = load(ROOT / "schemas" / name)
    resources = []
    for path in sorted((ROOT / "schemas").glob("*.json")):
        local = load(path)
        resources.append((local["$id"], Resource.from_contents(local)))
    return Draft202012Validator(
        schema, format_checker=FormatChecker(), registry=Registry().with_resources(resources)
    )


def test_persisted_candidate_and_session_match_phase_ah_contracts(tmp_path) -> None:
    store = AgentSessionStore(tmp_path / "agent.sqlite")
    created(store)
    spec = CandidateSpecification.parse(candidate())
    session = store.save_candidate(
        spec, event_id=uid(11), actor_id="qualified-agent", occurred_at=AT, expected_sequence=1
    )
    validator("agent-candidate-specification.schema.json").validate(spec.to_dict())
    validator("agent-session.schema.json").validate(session.to_dict())
