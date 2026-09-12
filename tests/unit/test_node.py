import asyncio
from datetime import UTC, datetime

import pytest

from nexus_os.capabilities import CapabilityRegistry
from nexus_os.node import NodeError, NodePrincipal, NodeState, NodeStore, RadNode
from tests.unit.test_capabilities import manifest, qualification, request

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)
READER = NodePrincipal("reader", frozenset({"node:read"}))
EXECUTOR = NodePrincipal("executor", frozenset({"node:execute", "node:read"}))
OPERATOR = NodePrincipal("operator", frozenset({"node:read", "node:drain"}))


def node(tmp_path, *, maximum=4):
    store = NodeStore(tmp_path / "node.db", "rad-node-01")
    subject = RadNode(store, CapabilityRegistry(), max_concurrency=maximum)

    async def add(operation, payload):
        assert operation == "compute.sum"
        return {"total": sum(payload["values"])}

    subject.bind(manifest(), object(), add, qualification(), at=NOW)
    return subject, store


def test_stable_identity_lifecycle_inventory_and_snapshot(tmp_path) -> None:
    subject, store = node(tmp_path)
    subject.start(at=NOW)
    assert subject.health() == "HEALTHY"
    snapshot = subject.snapshot(READER)
    assert snapshot.node_id == "rad-node-01"
    assert snapshot.state is NodeState.READY
    assert snapshot.capabilities == ("rad.compute.sum@1.0.0",)
    assert snapshot.revision >= 3
    assert len(subject.inventory(READER)) == 1
    subject.drain(OPERATOR, at=NOW)
    assert subject.snapshot(READER).state is NodeState.STOPPED
    store.close()


def test_execution_is_qualified_bounded_and_evidenced(tmp_path) -> None:
    subject, store = node(tmp_path)
    subject.start(at=NOW)
    result = asyncio.run(subject.execute(request(), {"values": [2, 3]}, EXECUTOR, at=NOW))
    assert result.output == {"total": 5}
    assert [event["kind"] for event in store.events()][-2:] == [
        "LEASE_ACQUIRED",
        "LEASE_COMPLETED",
    ]
    assert subject.snapshot(READER).active_leases == 0
    store.close()


def test_lifecycle_and_scopes_fail_closed(tmp_path) -> None:
    subject, store = node(tmp_path)
    with pytest.raises(NodeError, match="not accepting"):
        asyncio.run(subject.execute(request(), {}, EXECUTOR, at=NOW))
    with pytest.raises(NodeError, match="scope"):
        subject.inventory(NodePrincipal("none", frozenset()))
    subject.start(at=NOW)
    with pytest.raises(NodeError, match="only from STOPPED"):
        subject.start(at=NOW)
    with pytest.raises(NodeError, match="scope"):
        subject.drain(READER, at=NOW)
    store.close()


def test_restart_abandons_incomplete_lease_without_replay(tmp_path) -> None:
    subject, store = node(tmp_path)
    subject.start(at=NOW)
    store.append(
        "LEASE_ACQUIRED",
        {
            "lease_id": "00000000-0000-4000-8000-000000000001",
            "capability_id": "rad.compute.sum",
            "version": "1.0.0",
            "operation": "compute.sum",
            "manifest_digest": manifest().digest,
        },
        NOW,
    )
    store.close()

    reopened = NodeStore(tmp_path / "node.db", "rad-node-01")
    restarted = RadNode(reopened, CapabilityRegistry())
    restarted.start(at=NOW)
    assert restarted.health() == "HEALTHY"
    assert reopened.events()[-3]["kind"] == "LEASE_ABANDONED"
    reopened.close()


def test_node_identity_and_manifest_binding_are_immutable(tmp_path) -> None:
    _subject, store = node(tmp_path)
    store.close()
    with pytest.raises(NodeError, match="identity"):
        NodeStore(tmp_path / "node.db", "different-node")

    reopened = NodeStore(tmp_path / "node.db", "rad-node-01")
    changed = manifest()
    object.__setattr__(changed, "description", "Changed binding")
    with pytest.raises(NodeError, match="digest mismatch"):
        reopened.bind(changed, at=NOW)
    reopened.close()


def test_cancellation_releases_lease_and_records_terminal_event(tmp_path) -> None:
    store = NodeStore(tmp_path / "node.db", "rad-node-01")
    subject = RadNode(store, CapabilityRegistry(), max_concurrency=1)
    entered = asyncio.Event()

    async def blocked(operation, payload):
        entered.set()
        await asyncio.Event().wait()
        return {}

    subject.bind(manifest(), object(), blocked, qualification(), at=NOW)
    subject.start(at=NOW)

    async def scenario():
        task = asyncio.create_task(subject.execute(request(), {}, EXECUTOR, at=NOW))
        await entered.wait()
        with pytest.raises(NodeError, match="concurrency"):
            await subject.execute(request(), {}, EXECUTOR, at=NOW)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert subject.snapshot(READER).active_leases == 0
    assert store.events()[-1]["kind"] == "LEASE_CANCELLED"
    store.close()
