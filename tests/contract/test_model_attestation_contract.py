import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from tests.unit.test_model_attestation import manifest, qualify, records


def test_attested_qualification_satisfies_public_schema() -> None:
    document = manifest()
    value = qualify(document, records(document)).to_dict()
    qualification_schema = json.loads(Path("schemas/model-qualification.schema.json").read_text())
    attestation_schema = json.loads(
        Path("schemas/attested-model-qualification.schema.json").read_text()
    )
    registry = Registry().with_resource(
        "https://radforge.dev/schemas/model-qualification.schema.json",
        Resource.from_contents(qualification_schema),
    )
    Draft202012Validator(
        attestation_schema, registry=registry, format_checker=FormatChecker()
    ).validate(value)
