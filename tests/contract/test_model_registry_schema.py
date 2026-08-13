from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from nexus_os.model_registry import ModelQualificationRegistry
from scripts.validate_contracts import ROOT, load
from tests.unit.test_model_registry import REGISTERED_AT, attestation


def test_registry_record_matches_public_schema(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    record = store.register(
        attestation(),
        registered_at=REGISTERED_AT,
        registered_by="release-controller",
    )
    schema = load(ROOT / "schemas/model-qualification-registry-record.schema.json")
    resources = []
    for path in sorted((ROOT / "schemas").glob("*.json")):
        local_schema = load(path)
        resources.append((local_schema["$id"], Resource.from_contents(local_schema)))
    registry = Registry().with_resources(resources)
    Draft202012Validator(schema, format_checker=FormatChecker(), registry=registry).validate(
        record.to_dict()
    )
