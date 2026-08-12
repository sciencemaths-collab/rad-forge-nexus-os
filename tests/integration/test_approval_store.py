from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from nexus_os.approval import ApprovalError, ApprovalStatus, ApprovalStore
from nexus_os.domain import ActionEffect, RunId


def _request(store: ApprovalStore, now: datetime):
    return store.request(
        approval_id=uuid4(),
        project_id="project-1",
        run_id=RunId.new(),
        action_digest="sha256:" + "a" * 64,
        effect=ActionEffect.DESTRUCTIVE,
        requested_by="runtime",
        requested_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def test_approved_exact_action_is_consumed_once_and_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "approvals.sqlite3"
    now = datetime(2026, 8, 12, tzinfo=UTC)
    store = ApprovalStore(path)
    record = _request(store, now)
    approved = store.decide(
        record.approval_id,
        status=ApprovalStatus.APPROVED,
        decided_by="owner",
        decided_at=now + timedelta(seconds=1),
        reason="reviewed",
    )
    store.close()

    reopened = ApprovalStore(path)
    consumed = reopened.authorize_and_consume(
        approved.approval_id,
        project_id=approved.project_id,
        run_id=approved.run_id,
        action_digest=approved.action_digest,
        now=now + timedelta(seconds=2),
    )
    assert consumed.status is ApprovalStatus.CONSUMED
    with pytest.raises(ApprovalError, match="not approved"):
        reopened.authorize_and_consume(
            approved.approval_id,
            project_id=approved.project_id,
            run_id=approved.run_id,
            action_digest=approved.action_digest,
            now=now + timedelta(seconds=3),
        )


def test_denial_and_expiry_block_authorization(tmp_path: Path) -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    store = ApprovalStore(tmp_path / "approvals.sqlite3")
    denied = _request(store, now)
    store.decide(
        denied.approval_id,
        status=ApprovalStatus.DENIED,
        decided_by="owner",
        decided_at=now,
    )
    with pytest.raises(ApprovalError, match="not approved"):
        store.authorize_and_consume(
            denied.approval_id,
            project_id=denied.project_id,
            run_id=denied.run_id,
            action_digest=denied.action_digest,
            now=now,
        )

    expired = _request(store, now)
    store.decide(
        expired.approval_id,
        status=ApprovalStatus.APPROVED,
        decided_by="owner",
        decided_at=now,
    )
    with pytest.raises(ApprovalError, match="expired"):
        store.authorize_and_consume(
            expired.approval_id,
            project_id=expired.project_id,
            run_id=expired.run_id,
            action_digest=expired.action_digest,
            now=now + timedelta(minutes=6),
        )


def test_scope_mismatch_does_not_consume_approval(tmp_path: Path) -> None:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    store = ApprovalStore(tmp_path / "approvals.sqlite3")
    record = _request(store, now)
    store.decide(
        record.approval_id,
        status=ApprovalStatus.APPROVED,
        decided_by="owner",
        decided_at=now,
    )
    with pytest.raises(ApprovalError, match="scope"):
        store.authorize_and_consume(
            record.approval_id,
            project_id=record.project_id,
            run_id=record.run_id,
            action_digest="sha256:" + "b" * 64,
            now=now,
        )
    assert store.get(record.approval_id).status is ApprovalStatus.APPROVED


def test_concurrent_consumers_cannot_both_authorize(tmp_path: Path) -> None:
    path = tmp_path / "approvals.sqlite3"
    now = datetime(2026, 8, 12, tzinfo=UTC)
    store = ApprovalStore(path)
    record = _request(store, now)
    store.decide(record.approval_id, status=ApprovalStatus.APPROVED,
                 decided_by="owner", decided_at=now)
    store.close()

    def consume() -> bool:
        local = ApprovalStore(path)
        try:
            local.authorize_and_consume(
                record.approval_id, project_id=record.project_id, run_id=record.run_id,
                action_digest=record.action_digest, now=now,
            )
            return True
        except ApprovalError:
            return False
        finally:
            local.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: consume(), range(2)))
    assert sorted(outcomes) == [False, True]
