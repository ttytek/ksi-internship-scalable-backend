"""Lease reclaim and poison cap."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ksi.domain.entities import Submission, Task, User
from ksi.domain.enums import SubmissionStatus
from sqlalchemy.orm import Session

from ksi_checker.sweeper import reclaim_expired


def test_expired_running_requeued_under_cap(
    db_session: Session, sample_user: User, sample_task: Task
) -> None:
    past = datetime.now(UTC) - timedelta(seconds=5)
    sub = Submission(
        task_id=sample_task.id,
        user_id=sample_user.id,
        source_code="print(1)\n",
        language="python",
        status=SubmissionStatus.RUNNING,
        judge_attempts=1,
        lease_expires_at=past,
    )
    db_session.add(sub)
    db_session.commit()
    ids = reclaim_expired(db_session, now=datetime.now(UTC), max_attempts=3)
    assert sub.id in ids
    db_session.refresh(sub)
    assert sub.status == SubmissionStatus.QUEUED
    assert sub.judge_claim_id is None


def test_expired_running_at_cap_is_internal_error(
    db_session: Session, sample_user: User, sample_task: Task
) -> None:
    past = datetime.now(UTC) - timedelta(seconds=5)
    sub = Submission(
        task_id=sample_task.id,
        user_id=sample_user.id,
        source_code="print(1)\n",
        language="python",
        status=SubmissionStatus.RUNNING,
        judge_attempts=3,
        judge_claim_id=uuid4(),
        lease_expires_at=past,
    )
    db_session.add(sub)
    db_session.commit()
    ids = reclaim_expired(db_session, now=datetime.now(UTC), max_attempts=3)
    assert ids == []
    db_session.refresh(sub)
    assert sub.status == SubmissionStatus.INTERNAL_ERROR
    assert sub.judge_claim_id is None
