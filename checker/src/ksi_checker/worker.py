"""Checker replica: sticky drain, then Redis wake-up, Postgres claim, judge."""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from ksi.db.session import get_session_factory

from ksi_checker.broker import RedisBroker, SubmissionBroker
from ksi_checker.claim import Claimed, claim_by_id, claim_sticky
from ksi_checker.config import CheckerSettings, get_checker_settings
from ksi_checker.heartbeat import start_heartbeat
from ksi_checker.judge import load_job, persist_outcome, run_job
from ksi_checker.sweeper import sweep

logger = logging.getLogger(__name__)


def _consumer_name() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{threading.get_ident()}"


def _open_session():
    return get_session_factory()()


class Worker:
    def __init__(self, broker: SubmissionBroker, settings: CheckerSettings) -> None:
        self.broker = broker
        self.settings = settings
        self.sticky_task: UUID | None = None
        self.consumer = _consumer_name()
        self._last_sweep = 0.0

    def _lease_deadline(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=self.settings.checker_lease_seconds)

    def _maybe_sweep(self, *, autoclaim: bool) -> list[tuple[str, UUID]]:
        now = time.monotonic()
        if now - self._last_sweep < self.settings.checker_sweep_seconds:
            return []
        self._last_sweep = now
        session = _open_session()
        try:
            return sweep(
                session,
                self.broker,
                max_attempts=self.settings.checker_max_attempts,
                queued_repost_seconds=self.settings.checker_queued_repost_seconds,
                consumer=self.consumer,
                autoclaim_idle_ms=(
                    self.settings.checker_autoclaim_idle_seconds * 1000 if autoclaim else None
                ),
            )
        except Exception:
            logger.exception("Sweep failed")
            session.rollback()
            return []
        finally:
            session.close()

    def _handle_claimed(self, claimed: Claimed) -> None:
        self.sticky_task = claimed.task_id
        session = _open_session()
        try:
            job = load_job(session, claimed.id, claim_id=claimed.claim_id)
            session.commit()
        except Exception:
            logger.exception("Failed to load job %s", claimed.id)
            session.rollback()
            session.close()
            return
        session.close()
        if job is None:
            return

        stop, thread = start_heartbeat(
            claimed.id,
            claimed.claim_id,
            interval_seconds=self.settings.checker_heartbeat_seconds,
            lease_seconds=self.settings.checker_lease_seconds,
        )
        try:
            outcome = run_job(job)
            session = _open_session()
            try:
                persist_outcome(session, job, outcome, claim_id=claimed.claim_id)
            except Exception:
                logger.exception("Failed to persist %s", claimed.id)
                session.rollback()
            finally:
                session.close()
        except Exception:
            logger.exception("Judge failed for %s", claimed.id)
        finally:
            stop.set()
            thread.join(timeout=1)

    def _handle_message(self, msg_id: str, submission_id: UUID) -> bool:
        session = _open_session()
        try:
            claimed = claim_by_id(
                session,
                submission_id,
                lease_expires_at=self._lease_deadline(),
                max_attempts=self.settings.checker_max_attempts,
            )
        except Exception:
            logger.exception("Claim failed for %s", submission_id)
            session.rollback()
            session.close()
            return False
        session.close()
        if claimed is None:
            try:
                self.broker.ack(msg_id)
            except Exception:
                logger.exception("XACK failed for skipped %s", msg_id)
            return False
        try:
            self._handle_claimed(claimed)
            self.broker.ack(msg_id)
            return True
        except Exception:
            logger.exception("Failed processing %s", submission_id)
            return False

    def _try_sticky(self) -> bool:
        if self.sticky_task is None:
            return False
        session = _open_session()
        try:
            claimed = claim_sticky(
                session,
                self.sticky_task,
                lease_expires_at=self._lease_deadline(),
                max_attempts=self.settings.checker_max_attempts,
            )
        except Exception:
            logger.exception("Sticky claim failed")
            session.rollback()
            session.close()
            return False
        session.close()
        if claimed is None:
            self.sticky_task = None
            return False
        self._handle_claimed(claimed)
        return True

    def run_once(self, *, block_ms: int = 1000) -> None:
        pending = self._maybe_sweep(autoclaim=self.sticky_task is None)
        if self._try_sticky():
            return
        for msg_id, sid in pending:
            if self._handle_message(msg_id, sid):
                return
        try:
            messages = self.broker.read(self.consumer, block_ms=block_ms, count=1)
        except Exception:
            logger.exception("XREADGROUP failed")
            time.sleep(1)
            return
        for msg_id, sid in messages:
            self._handle_message(msg_id, sid)
            return

    def run(self) -> None:
        logger.info("Checker consumer %s starting", self.consumer)
        while True:
            self.run_once()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_checker_settings()
    os.environ["DATABASE_URL"] = settings.database_url
    from ksi.config import get_settings

    get_settings.cache_clear()
    broker = RedisBroker(settings.redis_url, settings.redis_stream, settings.redis_group)
    broker.ensure_group()
    n = max(1, settings.checker_concurrency)
    if n == 1:
        Worker(broker, settings).run()
        return
    threads = [
        threading.Thread(target=Worker(broker, settings).run, daemon=False)
        for _ in range(n)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
