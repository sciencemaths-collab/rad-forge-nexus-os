import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from tests.unit.test_model_qualification import evaluations, qualify


def test_derived_qualification_satisfies_public_schema() -> None:
    schema = json.loads(Path("schemas/model-qualification.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        qualify(evaluations()).to_dict()
    )
