import json
import zipfile

import pytest

from nexus_os.plugins import PluginError, PluginStore
from tests.unit.test_plugins import NOW, package


def test_tampered_payload_is_rejected_without_state(tmp_path):
    plugin, trust = package(tmp_path)
    with zipfile.ZipFile(plugin) as archive:
        manifest = archive.read("manifest.json")
        signature = archive.read("signature.ed25519")
    with zipfile.ZipFile(plugin, "w") as archive:
        archive.writestr("manifest.json", manifest)
        archive.writestr("acme_warehouse-1.2.3-py3-none-any.whl", b"tampered")
        archive.writestr("signature.ed25519", signature)
    store = PluginStore(tmp_path / "state", rad_version="0.2.0a8")
    with pytest.raises(PluginError, match="payload integrity"):
        store.install(
            plugin,
            trust,
            approved_permissions={"workspace.read"},
            installed_by="local.operator",
            installed_at=NOW,
        )
    assert store.list() == ()
    store.close()


def test_untrusted_publisher_and_modified_signature_are_rejected(tmp_path):
    plugin, trust = package(tmp_path)
    trust.write_text(json.dumps({"schema_version": "1.0", "publishers": {}}))
    store = PluginStore(tmp_path / "state", rad_version="0.2.0a8")
    with pytest.raises(PluginError, match="publisher is not trusted"):
        store.install(
            plugin,
            trust,
            approved_permissions={"workspace.read"},
            installed_by="local.operator",
            installed_at=NOW,
        )
    store.close()


def test_incompatible_plugin_is_rejected(tmp_path):
    plugin, trust = package(tmp_path)
    store = PluginStore(tmp_path / "state", rad_version="1.0.0")
    with pytest.raises(PluginError, match="incompatible"):
        store.install(
            plugin,
            trust,
            approved_permissions={"workspace.read"},
            installed_by="local.operator",
            installed_at=NOW,
        )
    store.close()


def test_managed_payload_tampering_fails_closed_before_enable(tmp_path):
    plugin, trust = package(tmp_path)
    store = PluginStore(tmp_path / "state", rad_version="0.2.0a8")
    record = store.install(
        plugin,
        trust,
        approved_permissions={"workspace.read"},
        installed_by="local.operator",
        installed_at=NOW,
    )
    record.payload_path.write_bytes(b"modified-after-install")
    with pytest.raises(PluginError, match="managed payload integrity"):
        store.enable("acme.warehouse", "1.2.3", actor="local.operator", at=NOW)
    store.close()
