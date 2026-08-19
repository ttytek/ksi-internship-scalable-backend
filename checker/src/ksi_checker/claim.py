"""Atomic Postgres claim. Redis is only a wake-up."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from ksi.domain.entities import Submission
from ksi.domain.enums import SubmissionStatus
from sqlalchemy import select, update
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Claimed:
    id: UUID
    task_id: UUID
    claim_id: UUID


def _values(claim_id: UUID, lease_expires_at: datetime) -> dict[str, object]:
    return {
        "status": SubmissionStatus.RUNNING,
        "judge_claim_id": claim_id,
        "lease_expires_at": lease_expires_at,
        "judge_attempts": Submission.judge_attempts + 1,
    }


def claim_by_id(
    session: Session,
    submission_id: UUID,
    *,
    lease_expires_at: datetime,
    max_attempts: int,
    claim_id: UUID | None = None,
) -> Claimed | None:
    cid = claim_id or uuid4()
    stmt = (
        update(Submission)
        .where(
            Submission.id == submission_id,
            Submission.status == SubmissionStatus.QUEUED,
            Submission.judge_attempts < max_attempts,
        )
        .values(**_values(cid, lease_expires_at))
        .returning(Submission.id, Submission.task_id)
    )
    row = session.execute(stmt).first()
    session.commit()
    if row is None:
        return None
    return Claimed(id=row.id, task_id=row.task_id, claim_id=cid)


def claim_sticky(
    session: Session,
    task_id: UUID,
    *,
    lease_expires_at: datetime,
    max_attempts: int,
    claim_id: UUID | None = None,
) -> Claimed | None:
    cid = claim_id or uuid4()
    dialect = session.get_bind().dialect.name
    inner = (
        select(Submission.id)
        .where(
            Submission.task_id == task_id,
            Submission.status == SubmissionStatus.QUEUED,
            Submission.judge_attempts < max_attempts,
        )
        .order_by(Submission.created_at.asc())
        .limit(1)
    )
    if dialect == "postgresql":
        inner = inner.with_for_update(skip_locked=True)
    stmt = (
        update(Submission)
        .where(
            Submission.id == inner.scalar_subquery(),
            Submission.status == SubmissionStatus.QUEUED,
            Submission.judge_attempts < max_attempts,
        )
        .values(**_values(cid, lease_expires_at))
        .returning(Submission.id, Submission.task_id)
    )
    row = session.execute(stmt).first()
    session.commit()
    if row is None:
        return None
    return Claimed(id=row.id, task_id=row.task_id, claim_id=cid)
