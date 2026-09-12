import json

from nexus_os.rad_cli import run
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
