from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from nexus_os.approval import ApprovalError, ApprovalStatus, ApprovalStore
from nexus_os.domain import ActionEffect, RunId


def test_invalid_effect_digest_and_time_window_are_rejected(tmp_path: Path) -> None:
    store = ApprovalStore(tmp_path / "approvals.sqlite3")
    now = datetime.now(UTC)
    for effect, digest, expiry in (
        (ActionEffect.READ_ONLY, "sha256:" + "a" * 64, now + timedelta(minutes=1)),
        (ActionEffect.SENSITIVE, "bad", now + timedelta(minutes=1)),
        (ActionEffect.SENSITIVE, "sha256:" + "a" * 64, now),
    ):
        with pytest.raises(ApprovalError):
            store.request(
                approval_id=uuid4(),
                project_id="p",
                run_id=RunId.new(),
                action_digest=digest,
                effect=effect,
                requested_by="runtime",
                requested_at=now,
                expires_at=expiry,
            )


def test_only_pending_records_can_be_decided(tmp_path: Path) -> None:
    store = ApprovalStore(tmp_path / "approvals.sqlite3")
    now = datetime.now(UTC)
    record = store.request(
        approval_id=uuid4(),
        project_id="p",
        run_id=RunId.new(),
        action_digest="sha256:" + "a" * 64,
        effect=ActionEffect.SENSITIVE,
        requested_by="runtime",
        requested_at=now,
        expires_at=now + timedelta(minutes=1),
    )
    store.decide(
        record.approval_id, status=ApprovalStatus.REVOKED, decided_by="owner", decided_at=now
    )
    with pytest.raises(ApprovalError, match="pending"):
        store.decide(
            record.approval_id, status=ApprovalStatus.APPROVED, decided_by="owner", decided_at=now
        )
