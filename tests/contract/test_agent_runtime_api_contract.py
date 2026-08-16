import asyncio

from tests.unit.test_agent_api import app, request
from tests.unit.test_agent_store import SESSION_ID


class RuntimeApi:
    def __init__(self):
        self.calls = []

    def start(self, session_id, identity, req, body):
        self.calls.append(("start", identity.actor_id, body))
        return _snapshot()

    def status(self, session_id):
        self.calls.append(("status",))
        return _snapshot()

    def pause(self, session_id, identity, req):
        self.calls.append(("pause", identity.actor_id))
        return {**_snapshot(), "run_state": "PAUSED"}

    def resume_execution(self, session_id, identity, req):
        self.calls.append(("resume", identity.actor_id))
        return {**_snapshot(), "run_state": "RUNNING"}

    def cancel(self, session_id, identity, req):
        self.calls.append(("cancel", identity.human))
        return {
            "runtime": {**_snapshot(), "run_state": "CANCELLED"},
            "session": {"state": "CANCELLED"},
        }

    async def prepare(self, session_id, identity, req, body):
        self.calls.append(("prepare", body))
        return {
            "task_id": "task",
            "task_kind": "mode.app_build.specification",
            "artifact": {"title": "Bound proposal"},
            "artifact_digest": "sha256:" + "a" * 64,
            "status": "PROPOSED",
        }

    def preparations(self, session_id):
        self.calls.append(("preparations",))
        return {
            "run_id": _snapshot()["run_id"],
            "tasks": [{"task_id": "task", "preparation_status": "PROPOSED"}],
        }

    def artifacts(self, session_id):
        self.calls.append(("artifacts",))
        return {"run_id": _snapshot()["run_id"], "artifacts": []}

    def artifact(self, session_id, task_id):
        self.calls.append(("artifact", task_id))
        return {
            "task_id": task_id,
            "name": "result.json",
            "content_base64": "e30K",
        }

    async def tick(self, session_id, identity, req, body):
        self.calls.append(("tick", body))
        return {"outcome": "IDLE", "runtime": _snapshot()}

    def decide_approval(self, session_id, approval_id, identity, req, body):
        self.calls.append(("approval", identity.human, body))
        return {"approval_id": str(approval_id), "status": body["status"]}

    def verify(self, session_id, identity, req):
        self.calls.append(("verify",))
        return {"passed": True, "session": {}}


def _snapshot():
    return {
        "run_id": "85000000-0000-4000-8000-000000000001",
        "graph_digest": "sha256:" + "1" * 64,
        "run_state": "READY",
        "task_states": {"task": "READY"},
        "revision": 1,
    }


def test_authenticated_runtime_routes_and_idempotent_mutations(tmp_path) -> None:
    runtime = RuntimeApi()
    subject, _ = app(tmp_path, [], runtime=runtime)
    base = f"/v1/agent/sessions/{SESSION_ID}/runtime"
    started = asyncio.run(
        subject.handle(
            request(
                "POST",
                base,
                body={"workspace_root": "/workspace/project"},
                key="runtime-start-0001",
            )
        )
    )
    replay = asyncio.run(
        subject.handle(
            request(
                "POST",
                base,
                body={"workspace_root": "/workspace/project"},
                key="runtime-start-0001",
            )
        )
    )
    status = asyncio.run(subject.handle(request("GET", base)))
    paused = asyncio.run(subject.handle(request("POST", base + "/pause", key="runtime-pause-0001")))
    resumed = asyncio.run(
        subject.handle(request("POST", base + "/resume", key="runtime-resume-001"))
    )
    prepared = asyncio.run(
        subject.handle(request("POST", base + "/preparations", key="runtime-prepare-001"))
    )
    manifest = asyncio.run(subject.handle(request("GET", base + "/preparations")))
    artifacts = asyncio.run(subject.handle(request("GET", base + "/artifacts")))
    artifact = asyncio.run(subject.handle(request("GET", base + "/artifacts/task")))
    tick = asyncio.run(subject.handle(request("POST", base + "/ticks", key="runtime-tick-0001")))
    verified = asyncio.run(
        subject.handle(request("POST", base + "/verify", key="runtime-verify-001"))
    )
    cancelled = asyncio.run(
        subject.handle(request("POST", base + "/cancel", key="runtime-cancel-001"))
    )
    assert (
        started.status,
        status.status,
        paused.status,
        resumed.status,
        prepared.status,
        manifest.status,
        artifacts.status,
        artifact.status,
        tick.status,
        verified.status,
        cancelled.status,
    ) == (
        201,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        200,
    )
    assert prepared.body["status"] == "PROPOSED"
    assert manifest.body["tasks"][0]["preparation_status"] == "PROPOSED"
    assert replay.headers["Idempotent-Replay"] == "true"
    assert [call[0] for call in runtime.calls] == [
        "start",
        "status",
        "pause",
        "resume",
        "prepare",
        "preparations",
        "artifacts",
        "artifact",
        "tick",
        "verify",
        "cancel",
    ]


def test_runtime_approval_requires_scope_body_and_uuid(tmp_path) -> None:
    runtime = RuntimeApi()
    subject, _ = app(tmp_path, [], runtime=runtime)
    path = f"/v1/agent/sessions/{SESSION_ID}/runtime/approvals/85000000-0000-4000-8000-000000000002"
    approved = asyncio.run(
        subject.handle(
            request(
                "POST",
                path,
                body={"status": "APPROVED", "reason": "Reviewed exact action."},
                key="runtime-approval-01",
            )
        )
    )
    invalid = asyncio.run(
        subject.handle(
            request(
                "POST",
                path,
                body={"status": "MAYBE"},
                key="runtime-approval-02",
            )
        )
    )
    assert approved.status == 200
    assert invalid.status == 400
