import asyncio
import io
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from nexus_os.local_model_cli import run_local_model_cli
from tests.unit.test_local_model_cli import arguments, transport


def test_generated_manifest_satisfies_public_schema(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"
    code = asyncio.run(
        run_local_model_cli(
            arguments(output),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            transport_factory=lambda sandbox: transport(),
        )
    )
    assert code == 0
    report_schema = json.loads(Path("schemas/model-evaluation-report.schema.json").read_text())
    manifest_schema = json.loads(
        Path("schemas/local-model-evaluation-manifest.schema.json").read_text()
    )
    registry = Registry().with_resource(
        "https://radforge.dev/schemas/model-evaluation-report.schema.json",
        Resource.from_contents(report_schema),
    )
    Draft202012Validator(
        manifest_schema, registry=registry, format_checker=FormatChecker()
    ).validate(json.loads(output.read_text()))
