"""Bump lease_expires_at while a job is running. Own short transactions."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta
from uuid import UUID

from ksi.db.session import get_session_factory
from ksi.domain.entities import Submission
from ksi.domain.enums import SubmissionStatus
from sqlalchemy import update

logger = logging.getLogger(__name__)


def heartbeat_once(
    submission_id: UUID,
    claim_id: UUID,
    lease_seconds: int,
) -> None:
    session = get_session_factory()()
    try:
        session.execute(
            update(Submission)
            .where(
                Submission.id == submission_id,
                Submission.judge_claim_id == claim_id,
                Submission.status == SubmissionStatus.RUNNING,
            )
            .values(lease_expires_at=datetime.now(UTC) + timedelta(seconds=lease_seconds))
        )
        session.commit()
    except Exception:
        logger.exception("Heartbeat failed for %s", submission_id)
        session.rollback()
    finally:
        session.close()


def start_heartbeat(
    submission_id: UUID,
    claim_id: UUID,
    *,
    interval_seconds: int,
    lease_seconds: int,
) -> tuple[threading.Event, threading.Thread]:
    stop = threading.Event()

    def _loop() -> None:
        while not stop.wait(interval_seconds):
            heartbeat_once(submission_id, claim_id, lease_seconds)

    thread = threading.Thread(
        target=_loop,
        name=f"ksi-heartbeat-{submission_id}",
        daemon=True,
    )
    thread.start()
    return stop, thread
