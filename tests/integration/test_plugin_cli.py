import hashlib
import json

from nexus_os.rad_cli import run
from tests.unit.test_plugin_runtime import wasm_result
from tests.unit.test_plugins import package


def test_end_user_plugin_cli_lifecycle(tmp_path, capsys):
    plugin, trust = package(tmp_path)
    config = tmp_path / "rad"
    common = ["--config-dir", str(config)]
    assert (
        run(
            [
                "plugins",
                "install",
                str(plugin),
                "--trust-store",
                str(trust),
                "--approve-permission",
                "workspace.read",
                *common,
            ]
        )
        == 0
    )
    installed = json.loads(capsys.readouterr().out)
    assert installed["state"] == "DISABLED"
    assert installed["execution_authorized"] is False

    assert run(["plugins", "enable", "acme.warehouse", "1.2.3", *common]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "ENABLED"
    assert run(["plugins", "list", *common]) == 0
    assert json.loads(capsys.readouterr().out)["plugins"][0]["state"] == "ENABLED"
    assert run(["plugins", "disable", "acme.warehouse", "1.2.3", *common]) == 0
    capsys.readouterr()
    assert run(["plugins", "uninstall", "acme.warehouse", "1.2.3", *common]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "UNINSTALLED"


def test_end_user_can_inspect_then_install_enable_and_doctor_plugin(tmp_path, capsys):
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
        "limitations": ["fixture_only"],
    }
    attestation_document = {
        **unsigned,
        "attestation_digest": "sha256:"
        + hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    attestation = tmp_path / "qualification.json"
    attestation.write_text(json.dumps(attestation_document))
    qualification_digest = "sha256:" + hashlib.sha256(attestation.read_bytes()).hexdigest()
    plugin, trust = package(
        tmp_path,
        permissions=[],
        qualification={"required": True, "attestation_sha256": qualification_digest},
        payload=wasm_result({"ok": True}),
    )
    config = tmp_path / "rad"
    common = ["--config-dir", str(config)]

    assert run(["plugins", "inspect", str(plugin), "--trust-store", str(trust), *common]) == 0
    review = json.loads(capsys.readouterr().out)
    assert review["activation_eligible"] is True
    assert review["permissions"] == []

    assert (
        run(
            [
                "plugins",
                "install",
                str(plugin),
                "--trust-store",
                str(trust),
                "--qualification",
                str(attestation),
                "--enable",
                *common,
            ]
        )
        == 0
    )
    installed = json.loads(capsys.readouterr().out)
    assert installed["state"] == "ENABLED"
    assert installed["execution_authorized"] is True

    assert run(["plugins", "doctor", *common]) == 0
    diagnosis = json.loads(capsys.readouterr().out)
    assert diagnosis["healthy"] is True
    assert diagnosis["plugins"][0]["runtime_readiness"] == "PASS"
