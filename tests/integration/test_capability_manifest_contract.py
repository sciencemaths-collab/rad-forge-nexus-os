import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from nexus_os.capabilities import CapabilityKind, CapabilityManifest, NetworkAccess, ResourceLimits
from nexus_os.domain import ActionEffect


def test_runtime_manifest_satisfies_public_contract() -> None:
    schema = json.loads(Path("schemas/capability-manifest.schema.json").read_text())
    value = CapabilityManifest(
        capability_id="rad.optimization.solve",
        version="1.0.0",
        kind=CapabilityKind.ENGINE_OPERATION,
        description="Solve a bounded optimization problem.",
        operations=("optimization.solve",),
        effects=frozenset({ActionEffect.READ_ONLY}),
        deterministic=True,
        network_access=NetworkAccess.DENIED,
        approval_required=False,
        qualification_required=True,
        resource_limits=ResourceLimits(60, 1024),
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value.canonical())
