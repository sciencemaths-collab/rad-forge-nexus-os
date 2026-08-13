import sqlite3
from datetime import timedelta
from uuid import UUID

import pytest

from nexus_os.model_attestation import attest_and_qualify
from nexus_os.model_qualification import ModelUse
from nexus_os.model_registry import (
    ModelQualificationRegistry,
    ModelRegistryError,
    RegistryStatus,
)
from tests.unit.test_model_attestation import ATTESTED_AT, manifest, records

QUALIFICATION_ID = UUID("60000000-0000-4000-8000-000000000100")
REGISTERED_AT = ATTESTED_AT + timedelta(minutes=1)


def attestation(*, qualification_id: UUID = QUALIFICATION_ID, fail_category: str | None = None):
    document = manifest(fail_category=fail_category)
    evidence = records(document)
    return attest_and_qualify(
        document,
        evidence,
        expected_count=7,
        expected_head=evidence[-1].record_hash,
        trusted_producers=frozenset({"independent-evaluator"}),
        qualification_id=qualification_id,
        attested_at=ATTESTED_AT,
        validity_seconds=3600,
    ).to_dict()


def register(store: ModelQualificationRegistry, document=None):
    return store.register(
        attestation() if document is None else document,
        registered_at=REGISTERED_AT,
        registered_by="release-controller",
    )


def test_register_and_authorize_exact_qualified_model(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    record = register(store)
    allowed = store.authorize(
        provider_id="local_openai",
        model_id="reference-model",
        adapter_version="1.0",
        use=ModelUse.SENSITIVE_ACTION_PROPOSAL,
        at=REGISTERED_AT,
    )
    assert record.status is RegistryStatus.ACTIVE
    assert allowed.qualification.qualification_id == QUALIFICATION_ID
    store.close()


def test_limited_qualification_denies_use_not_derived_from_results(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    register(store, attestation(fail_category="tool_selection"))
    with pytest.raises(ModelRegistryError, match="does not permit"):
        store.authorize(
            provider_id="local_openai",
            model_id="reference-model",
            adapter_version="1.0",
            use=ModelUse.TOOL_SELECTION,
            at=REGISTERED_AT,
        )


@pytest.mark.parametrize("field", ["provider_id", "model_id", "adapter_version"])
def test_authorization_requires_exact_model_binding(tmp_path, field) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    register(store)
    values = {
        "provider_id": "local_openai",
        "model_id": "reference-model",
        "adapter_version": "1.0",
    }
    values[field] = "wrong"
    with pytest.raises(ModelRegistryError, match="exact model binding"):
        store.authorize(**values, use=ModelUse.CLARIFICATION, at=REGISTERED_AT)


def test_exact_expiry_denies_use(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    record = register(store)
    with pytest.raises(ModelRegistryError, match="does not permit"):
        store.authorize(
            provider_id=record.qualification.provider_id,
            model_id=record.qualification.model_id,
            adapter_version=record.qualification.adapter_version,
            use=ModelUse.CLARIFICATION,
            at=record.qualification.expires_at,
        )


def test_revocation_is_one_way_and_immediately_denies_lookup(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    register(store)
    revoked = store.revoke(
        QUALIFICATION_ID,
        revoked_at=REGISTERED_AT + timedelta(minutes=1),
        revoked_by="security-reviewer",
        reason="evaluation corpus was later found compromised",
    )
    assert revoked.status is RegistryStatus.REVOKED
    with pytest.raises(ModelRegistryError, match="exact model binding"):
        store.authorize(
            provider_id="local_openai",
            model_id="reference-model",
            adapter_version="1.0",
            use=ModelUse.CLARIFICATION,
            at=REGISTERED_AT + timedelta(minutes=2),
        )
    with pytest.raises(ModelRegistryError, match="only an active"):
        store.revoke(
            QUALIFICATION_ID,
            revoked_at=REGISTERED_AT + timedelta(minutes=3),
            revoked_by="security-reviewer",
            reason="duplicate revocation",
        )


def test_new_attestation_atomically_supersedes_previous_record(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    old = register(store)
    new_id = UUID("60000000-0000-4000-8000-000000000101")
    new = register(store, attestation(qualification_id=new_id))
    assert store.get(old.qualification.qualification_id).status is RegistryStatus.SUPERSEDED
    assert new.status is RegistryStatus.ACTIVE
    active = store.authorize(
        provider_id="local_openai",
        model_id="reference-model",
        adapter_version="1.0",
        use=ModelUse.CLARIFICATION,
        at=REGISTERED_AT,
    )
    assert active.qualification.qualification_id == new_id


def test_duplicate_registration_rolls_back_supersession(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    register(store)
    with pytest.raises(ModelRegistryError, match="already exists"):
        register(store)
    assert store.get(QUALIFICATION_ID).status is RegistryStatus.ACTIVE


def test_registration_rejects_expired_or_predating_time(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    document = attestation()
    with pytest.raises(ModelRegistryError, match="not current"):
        store.register(
            document,
            registered_at=ATTESTED_AT - timedelta(seconds=1),
            registered_by="release-controller",
        )
    with pytest.raises(ModelRegistryError, match="not current"):
        store.register(
            document,
            registered_at=ATTESTED_AT + timedelta(hours=1),
            registered_by="release-controller",
        )


def test_tampered_attestation_digest_is_rejected(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    document = attestation()
    document["qualification"]["model_id"] = "tampered-model"
    with pytest.raises(ModelRegistryError, match="canonical verification"):
        register(store, document)


def test_secret_like_revocation_reason_is_rejected(tmp_path) -> None:
    store = ModelQualificationRegistry(tmp_path / "registry.sqlite")
    register(store)
    with pytest.raises(ModelRegistryError, match="secret-like"):
        store.revoke(
            QUALIFICATION_ID,
            revoked_at=REGISTERED_AT,
            revoked_by="security-reviewer",
            reason="ghp_abcdefghijklmnopqrstuvwxyz1234567890",
        )


def test_database_owner_tamper_fails_closed_after_restart(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    store = ModelQualificationRegistry(path)
    register(store)
    store.close()
    connection = sqlite3.connect(path)
    connection.execute("DROP TRIGGER immutable_model_qualification_content")
    connection.execute(
        "UPDATE model_qualifications SET model_id = ? WHERE qualification_id = ?",
        ("tampered-model", str(QUALIFICATION_ID)),
    )
    connection.commit()
    connection.close()
    reopened = ModelQualificationRegistry(path)
    with pytest.raises(ModelRegistryError, match="integrity validation"):
        reopened.get(QUALIFICATION_ID)


def test_delete_trigger_preserves_history(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    store = ModelQualificationRegistry(path)
    register(store)
    with pytest.raises(sqlite3.IntegrityError, match="append preserving"):
        store._connection.execute(
            "DELETE FROM model_qualifications WHERE qualification_id = ?",
            (str(QUALIFICATION_ID),),
        )
