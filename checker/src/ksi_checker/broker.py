"""Redis Streams competing-consumer wrapper (wake-up only; Postgres is the lock)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

import redis
from redis.exceptions import ResponseError

STREAM_MAXLEN = 10_000


class SubmissionBroker(Protocol):
    def ensure_group(self) -> None: ...

    def publish(self, submission_id: UUID) -> None: ...

    def read(
        self, consumer: str, block_ms: int, count: int = 1
    ) -> list[tuple[str, UUID]]: ...

    def ack(self, msg_id: str) -> None: ...

    def autoclaim(self, consumer: str, min_idle_ms: int) -> list[tuple[str, UUID]]: ...


class RedisBroker:
    def __init__(self, url: str, stream: str, group: str) -> None:
        self._r = redis.Redis.from_url(url, decode_responses=True)
        self.stream = stream
        self.group = group

    def ensure_group(self) -> None:
        try:
            self._r.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def publish(self, submission_id: UUID) -> None:
        self._r.xadd(
            self.stream,
            {"submission_id": str(submission_id)},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )

    def read(
        self, consumer: str, block_ms: int, count: int = 1
    ) -> list[tuple[str, UUID]]:
        resp = self._r.xreadgroup(
            self.group,
            consumer,
            {self.stream: ">"},
            count=count,
            block=block_ms,
        )
        return _parse_entries(resp)

    def ack(self, msg_id: str) -> None:
        self._r.xack(self.stream, self.group, msg_id)

    def autoclaim(self, consumer: str, min_idle_ms: int) -> list[tuple[str, UUID]]:
        result = self._r.xautoclaim(
            self.stream,
            self.group,
            consumer,
            min_idle_ms,
            "0-0",
            count=20,
        )
        messages = result[1] if result else []
        out: list[tuple[str, UUID]] = []
        for msg_id, fields in messages:
            sid = (fields or {}).get("submission_id")
            if sid:
                out.append((msg_id, UUID(str(sid))))
        return out


def _parse_entries(resp: object) -> list[tuple[str, UUID]]:
    out: list[tuple[str, UUID]] = []
    if not resp:
        return out
    for _stream, entries in resp:  # type: ignore[misc]
        for msg_id, fields in entries:
            sid = (fields or {}).get("submission_id")
            if sid:
                out.append((msg_id, UUID(str(sid))))
    return out


@dataclass
class InMemoryBroker:
    """In-process stream for tests."""

    queue: list[tuple[str, UUID]] = field(default_factory=list)
    pending: dict[str, tuple[str, UUID]] = field(default_factory=dict)
    _seq: int = 0

    def ensure_group(self) -> None:
        return None

    def publish(self, submission_id: UUID) -> None:
        self._seq += 1
        self.queue.append((str(self._seq), submission_id))

    def read(
        self, consumer: str, block_ms: int, count: int = 1
    ) -> list[tuple[str, UUID]]:
        del consumer, block_ms
        taken: list[tuple[str, UUID]] = []
        while self.queue and len(taken) < count:
            item = self.queue.pop(0)
            self.pending[item[0]] = item
            taken.append(item)
        return taken

    def ack(self, msg_id: str) -> None:
        self.pending.pop(msg_id, None)

    def autoclaim(self, consumer: str, min_idle_ms: int) -> list[tuple[str, UUID]]:
        del consumer, min_idle_ms
        items = list(self.pending.values())
        return items


def collect_ids(entries: Sequence[tuple[str, UUID]]) -> list[UUID]:
    return [sid for _mid, sid in entries]
