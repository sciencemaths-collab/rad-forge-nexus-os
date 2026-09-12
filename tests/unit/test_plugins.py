import base64
import hashlib
import json
import zipfile
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from nexus_os.plugins import PluginError, PluginStore, inspect_plugin_package

NOW = datetime(2026, 9, 12, 15, tzinfo=UTC)


def package(tmp_path, *, permissions=None, qualification=None, payload=b"wasm-bytes"):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    trust = tmp_path / "trust.json"
    trust.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "publishers": {"acme.plugins": base64.b64encode(public).decode()},
            }
        )
    )
    manifest = {
        "schema_version": "1.0",
        "plugin_id": "acme.warehouse",
        "version": "1.2.3",
        "publisher_id": "acme.plugins",
        "rad_version": {"minimum": "0.2.0", "maximum_exclusive": "0.3.0"},
        "payload": {
            "filename": "acme_warehouse-1.2.3.wasm",
            "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        },
        "permissions": ["workspace.read"] if permissions is None else permissions,
        "capabilities": ["acme.warehouse.allocate@1.0.0"],
        "qualification": qualification or {"required": False, "attestation_sha256": None},
        "runtime": {
            "kind": "wasm-v1",
            "operations": ["warehouse.allocate"],
            "max_fuel": 100_000,
            "max_memory_pages": 4,
        },
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    plugin = tmp_path / "plugin.radplug"
    with zipfile.ZipFile(plugin, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(manifest["payload"]["filename"], payload)
        archive.writestr("signature.ed25519", private.sign(canonical))
    return plugin, trust


def test_install_is_verified_disabled_and_audited(tmp_path):
    plugin, trust = package(tmp_path)
    store = PluginStore(tmp_path / "state", rad_version="0.2.0a8")
    record = store.install(
        plugin,
        trust,
        approved_permissions={"workspace.read"},
        installed_by="local.operator",
        installed_at=NOW,
    )
    assert record.state == "DISABLED"
    assert record.payload_path.read_bytes() == b"wasm-bytes"
    assert record.public_dict()["execution_authorized"] is False
    assert store.events()[0]["action"] == "INSTALL"
    store.close()


def test_inspect_verifies_signature_and_exposes_exact_review_without_installing(tmp_path):
    plugin, trust = package(tmp_path)
    review = inspect_plugin_package(plugin, trust)
    assert review["plugin_id"] == "acme.warehouse"
    assert review["permissions"] == ["workspace.read"]
    assert review["install_state"] == "NOT_INSTALLED"
    assert review["activation_eligible"] is False
    assert review["package_digest"].startswith("sha256:")


def test_enable_update_rollback_and_disabled_uninstall(tmp_path):
    plugin, trust = package(tmp_path)
    store = PluginStore(tmp_path / "state", rad_version="0.2.0a8")
    store.install(
        plugin,
        trust,
        approved_permissions={"workspace.read"},
        installed_by="local.operator",
        installed_at=NOW,
    )
    assert (
        store.enable("acme.warehouse", "1.2.3", actor="local.operator", at=NOW).state == "ENABLED"
    )
    with pytest.raises(PluginError, match="disabled"):
        store.uninstall("acme.warehouse", "1.2.3", actor="local.operator", at=NOW)
    store.disable("acme.warehouse", "1.2.3", actor="local.operator", at=NOW)
    store.uninstall("acme.warehouse", "1.2.3", actor="local.operator", at=NOW)
    assert store.list() == ()
    assert [item["action"] for item in store.events()] == [
        "INSTALL",
        "ENABLED",
        "DISABLED",
        "UNINSTALL",
    ]
    store.close()


def test_exact_permissions_are_required(tmp_path):
    plugin, trust = package(tmp_path, permissions=["network", "secrets"])
    store = PluginStore(tmp_path / "state", rad_version="0.2.0a8")
    with pytest.raises(PluginError, match="exact plugin permission"):
        store.install(
            plugin,
            trust,
            approved_permissions={"network"},
            installed_by="local.operator",
            installed_at=NOW,
        )
    store.close()


def test_required_qualification_is_digest_bound(tmp_path):
    attestation = tmp_path / "qualification.json"
    attestation.write_bytes(b"qualified-evidence")
    digest = "sha256:" + hashlib.sha256(attestation.read_bytes()).hexdigest()
    plugin, trust = package(
        tmp_path, qualification={"required": True, "attestation_sha256": digest}
    )
    store = PluginStore(tmp_path / "state", rad_version="0.2.0a8")
    with pytest.raises(PluginError, match="qualification attestation is required"):
        store.install(
            plugin,
            trust,
            approved_permissions={"workspace.read"},
            installed_by="local.operator",
            installed_at=NOW,
        )
    record = store.install(
        plugin,
        trust,
        approved_permissions={"workspace.read"},
        installed_by="local.operator",
        installed_at=NOW,
        qualification_attestation=attestation,
    )
    assert record.qualification_digest == digest
    store.close()
