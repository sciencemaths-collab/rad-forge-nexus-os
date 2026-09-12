import sqlite3
from datetime import UTC, datetime

import pytest

from nexus_os.capabilities import CapabilityRegistry
from nexus_os.node import NodeError, NodeStore, RadNode
from tests.unit.test_node import READER


def test_event_chain_tampering_degrades_health_and_blocks_snapshot(tmp_path) -> None:
    path = tmp_path / "node.db"
    store = NodeStore(path, "rad-node-01")
    node = RadNode(store, CapabilityRegistry())
    node.start(at=datetime(2026, 9, 12, tzinfo=UTC))
    connection = sqlite3.connect(path)
    connection.execute("DROP TRIGGER immutable_node_event")
    connection.execute("UPDATE node_events SET payload_json='{}' WHERE sequence=1")
    connection.commit()
    connection.close()
    assert node.health() == "DEGRADED"
    with pytest.raises(NodeError, match="integrity"):
        node.snapshot(READER)
    store.close()


def test_event_payload_is_redacted_before_persistence(tmp_path) -> None:
    store = NodeStore(tmp_path / "node.db", "rad-node-01")
    store.append(
        "TEST",
        {"token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"},
        datetime(2026, 9, 12, tzinfo=UTC),
    )
    encoded = str(store.events())
    assert "ghp_" not in encoded
    assert "<redacted>" in encoded
    store.close()


def test_capability_binding_tampering_degrades_health(tmp_path) -> None:
    from tests.unit.test_capabilities import manifest

    path = tmp_path / "node.db"
    store = NodeStore(path, "rad-node-01")
    store.bind(manifest(), at=datetime(2026, 9, 12, tzinfo=UTC))
    node = RadNode(store, CapabilityRegistry())
    connection = sqlite3.connect(path)
    connection.execute("DROP TRIGGER immutable_node_capability")
    connection.execute("UPDATE node_capabilities SET manifest_json='{}'")
    connection.commit()
    connection.close()
    assert node.health() == "DEGRADED"
    store.close()
