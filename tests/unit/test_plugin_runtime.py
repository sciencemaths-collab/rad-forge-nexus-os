import hashlib
import json

import pytest
import wasmtime

from nexus_os.plugin_runtime import PluginRuntimeError, WasmPluginAdapter
from nexus_os.plugins import PluginStore
from tests.unit.test_plugins import NOW, package


def wasm_result(document):
    raw = json.dumps(document, separators=(",", ":")).encode()
    escaped = "".join(f"\\{byte:02x}" for byte in raw)
    packed = len(raw)
    return wasmtime.wat2wasm(
        f"""(module
          (memory (export "memory") 1)
          (data (i32.const 0) "{escaped}")
          (func (export "alloc") (param i32) (result i32) i32.const 1024)
          (func (export "handle") (param i32 i32) (result i64) i64.const {packed})
        )"""
    )


def activated(tmp_path, payload):
    attestation = tmp_path / "qualification.json"
    unsigned = {
        "schema_version": "1.0",
        "plugin_id": "acme.warehouse",
        "plugin_version": "1.2.3",
        "capability_id": "acme.warehouse.allocate",
        "capability_version": "1.0.0",
        "runtime_kind": "wasm-v1",
        "outcome": "QUALIFIED",
        "evaluated_at": "2026-09-12T14:00:00Z",
        "expires_at": "2026-10-12T14:00:00Z",
        "benchmark_digest": "sha256:" + "1" * 64,
        "limitations": [],
    }
    attestation_document = {
        **unsigned,
        "attestation_digest": "sha256:"
        + hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    attestation.write_bytes(
        json.dumps(attestation_document, sort_keys=True, separators=(",", ":")).encode()
    )
    digest = "sha256:" + hashlib.sha256(attestation.read_bytes()).hexdigest()
    plugin, trust = package(
        tmp_path,
        permissions=[],
        qualification={"required": True, "attestation_sha256": digest},
        payload=payload,
    )
    store = PluginStore(tmp_path / "state", rad_version="0.2.0a8")
    store.install(
        plugin,
        trust,
        approved_permissions=set(),
        installed_by="local.operator",
        installed_at=NOW,
        qualification_attestation=attestation,
    )
    store.enable("acme.warehouse", "1.2.3", actor="local.operator", at=NOW)
    return store


def test_wasm_plugin_executes_canonical_json_without_host_access(tmp_path):
    store = activated(tmp_path, wasm_result({"accepted": True, "source": "wasm"}))
    status = store.get("acme.warehouse", "1.2.3").public_dict()
    assert status["activation_configured"] is True
    assert status["execution_authorized"] is False
    adapter = WasmPluginAdapter(store, "acme.warehouse", "1.2.3")
    assert adapter.manifest().network_access.value == "DENIED"
    import asyncio

    result = asyncio.run(adapter.execute("warehouse.allocate", {"units": 4}))
    assert result == {"accepted": True, "source": "wasm"}
    store.close()


def test_host_imports_are_rejected(tmp_path):
    payload = wasmtime.wat2wasm(
        """(module
          (import "wasi_snapshot_preview1" "fd_write" (func))
          (memory (export "memory") 1)
          (func (export "alloc") (param i32) (result i32) i32.const 0)
          (func (export "handle") (param i32 i32) (result i64) i64.const 0)
        )"""
    )
    store = activated(tmp_path, payload)
    with pytest.raises(PluginRuntimeError, match="host imports are denied"):
        WasmPluginAdapter(store, "acme.warehouse", "1.2.3")
    store.close()


def test_permissions_are_rejected_at_activation(tmp_path):
    plugin, trust = package(tmp_path, payload=wasm_result({"ok": True}))
    store = PluginStore(tmp_path / "state", rad_version="0.2.0a8")
    store.install(
        plugin,
        trust,
        approved_permissions={"workspace.read"},
        installed_by="local.operator",
        installed_at=NOW,
    )
    store.enable("acme.warehouse", "1.2.3", actor="local.operator", at=NOW)
    with pytest.raises(PluginRuntimeError, match="permits no host permissions"):
        WasmPluginAdapter(store, "acme.warehouse", "1.2.3")
    store.close()


def test_tampered_qualification_is_rejected_at_activation(tmp_path):
    store = activated(tmp_path, wasm_result({"ok": True}))
    qualification = store.get("acme.warehouse", "1.2.3").payload_path.parent / "qualification.json"
    qualification.write_bytes(b"tampered")
    with pytest.raises(PluginRuntimeError, match="qualification integrity"):
        WasmPluginAdapter(store, "acme.warehouse", "1.2.3")
    store.close()


def test_fuel_exhaustion_stops_unbounded_plugin(tmp_path):
    payload = wasmtime.wat2wasm(
        """(module
          (memory (export "memory") 1)
          (func (export "alloc") (param i32) (result i32) i32.const 0)
          (func (export "handle") (param i32 i32) (result i64)
            (loop $forever (br $forever))
            i64.const 0)
        )"""
    )
    store = activated(tmp_path, payload)
    adapter = WasmPluginAdapter(store, "acme.warehouse", "1.2.3")
    import asyncio

    with pytest.raises(PluginRuntimeError, match="failed safely"):
        asyncio.run(adapter.execute("warehouse.allocate", {}))
    store.close()
