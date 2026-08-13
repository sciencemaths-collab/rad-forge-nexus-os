import asyncio
import json

from tests.unit.test_agent_api import app, request
from tests.unit.test_agent_controller import proposal
from tests.unit.test_agent_store import SESSION_ID


def test_clarification_reenters_controller_and_returns_review(tmp_path) -> None:
    first = proposal(ready=False, questions=["Which operating system?"])
    second = proposal()
    subject, _ = app(tmp_path, [json.dumps(first), json.dumps(second)])
    created = asyncio.run(
        subject.handle(
            request(
                "POST",
                "/v1/agent/sessions",
                body={"project_id": "reference_agent", "objective": "Build an app."},
                key="create-session-0001",
            )
        )
    )
    clarified = asyncio.run(
        subject.handle(
            request(
                "POST",
                f"/v1/agent/sessions/{SESSION_ID}/clarifications",
                body={"response": "Target Linux."},
                key="clarify-session-01",
            )
        )
    )
    assert created.body["state"] == "CLARIFICATION_REQUIRED"
    assert clarified.body["state"] == "USER_REVIEW"
    assert len(clarified.body["events"]) == 5
