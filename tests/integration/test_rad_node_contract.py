import json
from datetime import UTC, datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from nexus_os.capabilities import CapabilityRegistry
from nexus_os.node import NodeStore, RadNode
from tests.unit.test_node import READER


def test_node_snapshot_satisfies_public_schema(tmp_path) -> None:
    store = NodeStore(tmp_path / "node.db", "rad-node-01")
    node = RadNode(store, CapabilityRegistry())
    node.start(at=datetime(2026, 9, 12, tzinfo=UTC))
    schema = json.loads(Path("schemas/rad-node.schema.json").read_text())
    Draft202012Validator(schema).validate(node.snapshot(READER).canonical())
    store.close()
