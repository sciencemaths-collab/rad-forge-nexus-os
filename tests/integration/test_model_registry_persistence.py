from nexus_os.model_qualification import ModelUse
from nexus_os.model_registry import ModelQualificationRegistry, RegistryStatus
from tests.unit.test_model_registry import QUALIFICATION_ID, REGISTERED_AT, register


def test_registered_qualification_and_revocation_survive_restart(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    first = ModelQualificationRegistry(path)
    register(first)
    first.close()

    second = ModelQualificationRegistry(path)
    allowed = second.authorize(
        provider_id="local_openai",
        model_id="reference-model",
        adapter_version="1.0",
        use=ModelUse.CLARIFICATION,
        at=REGISTERED_AT,
    )
    assert allowed.qualification.qualification_id == QUALIFICATION_ID
    second.revoke(
        QUALIFICATION_ID,
        revoked_at=REGISTERED_AT,
        revoked_by="security-reviewer",
        reason="operator-directed withdrawal",
    )
    second.close()

    third = ModelQualificationRegistry(path)
    assert third.get(QUALIFICATION_ID).status is RegistryStatus.REVOKED
