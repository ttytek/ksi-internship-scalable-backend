"""Claim lock and attempt cap."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ksi.domain.entities import Submission, Task, User
from ksi.domain.enums import SubmissionStatus
from sqlalchemy.orm import Session

from ksi_checker.claim import claim_by_id, claim_sticky


def _queued(session: Session, user: User, task: Task, attempts: int = 0) -> Submission:
    sub = Submission(
        task_id=task.id,
        user_id=user.id,
        source_code="print(1)\n",
        language="python",
        status=SubmissionStatus.QUEUED,
        judge_attempts=attempts,
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def test_claim_by_id_sets_running(
    db_session: Session, sample_user: User, sample_task: Task
) -> None:
    sub = _queued(db_session, sample_user, sample_task)
    lease = datetime.now(UTC) + timedelta(seconds=30)
    claimed = claim_by_id(db_session, sub.id, lease_expires_at=lease, max_attempts=3)
    assert claimed is not None
    assert claimed.id == sub.id
    assert claimed.task_id == sample_task.id
    db_session.refresh(sub)
    assert sub.status == SubmissionStatus.RUNNING
    assert sub.judge_claim_id == claimed.claim_id
    assert sub.judge_attempts == 1


def test_claim_by_id_skips_non_queued(
    db_session: Session, sample_user: User, sample_task: Task
) -> None:
    sub = _queued(db_session, sample_user, sample_task)
    sub.status = SubmissionStatus.RUNNING
    db_session.commit()
    claimed = claim_by_id(
        db_session,
        sub.id,
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=30),
        max_attempts=3,
    )
    assert claimed is None


def test_claim_respects_attempt_cap(
    db_session: Session, sample_user: User, sample_task: Task
) -> None:
    sub = _queued(db_session, sample_user, sample_task, attempts=3)
    claimed = claim_by_id(
        db_session,
        sub.id,
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=30),
        max_attempts=3,
    )
    assert claimed is None


def test_sticky_prefers_same_task(
    db_session: Session, sample_user: User, sample_task: Task
) -> None:
    other = Task(
        id=uuid4(),
        slug="other",
        title="Other",
        statement="s",
        time_limit_ms=1000,
        memory_limit_mb=64,
        is_published=True,
    )
    db_session.add(other)
    db_session.flush()
    first = _queued(db_session, sample_user, sample_task)
    second = _queued(db_session, sample_user, sample_task)
    other_sub = _queued(db_session, sample_user, other)
    lease = datetime.now(UTC) + timedelta(seconds=30)
    a = claim_by_id(db_session, first.id, lease_expires_at=lease, max_attempts=3)
    assert a is not None
    b = claim_sticky(
        db_session, sample_task.id, lease_expires_at=lease, max_attempts=3
    )
    assert b is not None
    assert b.id == second.id
    db_session.refresh(other_sub)
    assert other_sub.status == SubmissionStatus.QUEUED


def test_sticky_empty_returns_none(
    db_session: Session, sample_task: Task
) -> None:
    claimed = claim_sticky(
        db_session,
        sample_task.id,
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=30),
        max_attempts=3,
    )
    assert claimed is None
