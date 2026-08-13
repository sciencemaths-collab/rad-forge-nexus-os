import sqlite3

import pytest

from nexus_os.agent_store import (
    AgentSessionStore,
    AgentState,
    AgentStoreError,
    CandidateSpecification,
)
from tests.unit.test_agent_store import AT, SESSION_ID, candidate, created, uid


def test_candidate_and_event_history_survive_restart(tmp_path) -> None:
    path = tmp_path / "agent.sqlite"
    first = AgentSessionStore(path)
    created(first)
    first.save_candidate(
        CandidateSpecification.parse(candidate()),
        event_id=uid(11),
        actor_id="qualified-agent",
        occurred_at=AT,
        expected_sequence=1,
    )
    first.close()
    second = AgentSessionStore(path)
    assert second.get(SESSION_ID).state is AgentState.SPECIFICATION_READY
    assert second.get_candidate(SESSION_ID).revision == 1


def test_database_owner_event_tamper_fails_closed(tmp_path) -> None:
    path = tmp_path / "agent.sqlite"
    store = AgentSessionStore(path)
    created(store)
    store.close()
    connection = sqlite3.connect(path)
    connection.execute("DROP TRIGGER no_agent_event_update")
    connection.execute("UPDATE agent_events SET sequence = 3")
    connection.commit()
    connection.close()
    reopened = AgentSessionStore(path)
    with pytest.raises(AgentStoreError, match="integrity validation"):
        reopened.get(SESSION_ID)


def test_event_and_candidate_delete_triggers_preserve_history(tmp_path) -> None:
    store = AgentSessionStore(tmp_path / "agent.sqlite")
    created(store)
    store.save_candidate(
        CandidateSpecification.parse(candidate()),
        event_id=uid(11),
        actor_id="qualified-agent",
        occurred_at=AT,
        expected_sequence=1,
    )
    with pytest.raises(sqlite3.IntegrityError, match="append only"):
        store._connection.execute("DELETE FROM agent_events")
    with pytest.raises(sqlite3.IntegrityError, match="append only"):
        store._connection.execute("DELETE FROM agent_candidates")
