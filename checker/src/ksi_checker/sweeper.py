"""Reclaim expired leases and re-publish stuck queued rows."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from ksi.domain.entities import Submission
from ksi.domain.enums import SubmissionStatus
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from ksi_checker.broker import SubmissionBroker

logger = logging.getLogger(__name__)


def reclaim_expired(
    session: Session,
    *,
    now: datetime,
    max_attempts: int,
) -> list[UUID]:
    """Expired running jobs: poison at cap, otherwise requeue. Returns ids to publish."""
    poison = (
        update(Submission)
        .where(
            Submission.status == SubmissionStatus.RUNNING,
            Submission.lease_expires_at.is_not(None),
            Submission.lease_expires_at < now,
            Submission.judge_attempts >= max_attempts,
        )
        .values(
            status=SubmissionStatus.INTERNAL_ERROR,
            compile_message="Judge attempt cap reached after worker loss",
            judged_at=now,
            lease_expires_at=None,
            judge_claim_id=None,
        )
    )
    session.execute(poison)

    stmt = (
        update(Submission)
        .where(
            Submission.status == SubmissionStatus.RUNNING,
            Submission.lease_expires_at.is_not(None),
            Submission.lease_expires_at < now,
            Submission.judge_attempts < max_attempts,
        )
        .values(
            status=SubmissionStatus.QUEUED,
            judge_claim_id=None,
            lease_expires_at=None,
        )
        .returning(Submission.id)
    )
    ids = [row.id for row in session.execute(stmt)]
    session.commit()
    return ids


def queued_to_republish(session: Session, *, older_than: datetime) -> list[UUID]:
    rows = session.execute(
        select(Submission.id).where(
            Submission.status == SubmissionStatus.QUEUED,
            or_(
                and_(
                    Submission.queue_published_at.is_(None),
                    Submission.created_at < older_than,
                ),
                Submission.queue_published_at < older_than,
            ),
        )
    ).all()
    return [row.id for row in rows]


def mark_published(session: Session, ids: list[UUID], *, now: datetime) -> None:
    if not ids:
        return
    session.execute(
        update(Submission)
        .where(Submission.id.in_(ids))
        .values(queue_published_at=now)
    )
    session.commit()


def sweep(
    session: Session,
    broker: SubmissionBroker,
    *,
    max_attempts: int,
    queued_repost_seconds: int,
    consumer: str,
    autoclaim_idle_ms: int | None,
) -> list[tuple[str, UUID]]:
    now = datetime.now(UTC)
    reclaimed: list[UUID] = []
    for sid in reclaim_expired(session, now=now, max_attempts=max_attempts):
        try:
            broker.publish(sid)
            reclaimed.append(sid)
        except Exception:
            logger.exception("Sweeper failed to publish reclaimed %s", sid)
    mark_published(session, reclaimed, now=now)

    cutoff = now - timedelta(seconds=queued_repost_seconds)
    stale: list[UUID] = []
    for sid in queued_to_republish(session, older_than=cutoff):
        try:
            broker.publish(sid)
            stale.append(sid)
        except Exception:
            logger.exception("Sweeper failed to re-publish queued %s", sid)
    mark_published(session, stale, now=now)

    if autoclaim_idle_ms is None:
        return []
    try:
        return broker.autoclaim(consumer, autoclaim_idle_ms)
    except Exception:
        logger.exception("XAUTOCLAIM failed")
        return []
