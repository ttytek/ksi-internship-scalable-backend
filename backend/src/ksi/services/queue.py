"""Publish submission ids onto the Redis Stream (wake-up for checkers)."""

from __future__ import annotations

import logging
from functools import lru_cache
from uuid import UUID

from ksi.config import get_settings

logger = logging.getLogger(__name__)

STREAM_MAXLEN = 10_000


@lru_cache
def _redis():
    import redis

    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def publish_submission(submission_id: UUID) -> bool:
    """XADD the id. Failures are logged; the checker sweeper re-publishes queued rows."""
    settings = get_settings()
    try:
        _redis().xadd(
            settings.redis_stream,
            {"submission_id": str(submission_id)},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to publish submission %s to Redis; sweeper will retry",
            submission_id,
        )
        return False
