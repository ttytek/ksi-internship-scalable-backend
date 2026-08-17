"""Podpina zip z testami głównymi jako nową, niezmienną rewizję."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from ksi.config import get_settings
from ksi.domain.entities import Task, TaskTest, TaskTestPackRevision
from ksi.domain.enums import TestVisibility
from ksi.services.storage import ObjectStorage, main_pack_key, require_storage
from ksi.services.test_pack import inspect_pack


def next_revision_number(session: Session, task_id: object) -> int:
    current = (
        session.query(func.max(TaskTestPackRevision.revision))
        .filter(TaskTestPackRevision.task_id == task_id)
        .scalar()
    )
    return int(current or 0) + 1


def attach_main_pack(
    session: Session,
    task: Task,
    zip_bytes: bytes,
    *,
    storage: ObjectStorage | None = None,
    prefix: str | None = None,
) -> TaskTestPackRevision:
    """Upload next revision and insert TaskTest rows from the manifest."""
    cases = inspect_pack(zip_bytes)
    store = storage if storage is not None else require_storage()
    key_prefix = get_settings().s3_prefix if prefix is None else prefix
    revision_no = next_revision_number(session, task.id)

    session.query(TaskTestPackRevision).filter(
        TaskTestPackRevision.task_id == task.id,
        TaskTestPackRevision.is_current.is_(True),
    ).update({"is_current": False})

    s3_key = main_pack_key(key_prefix, task.id, revision_no)
    etag = store.put_bytes(s3_key, zip_bytes)

    revision = TaskTestPackRevision(
        task_id=task.id,
        revision=revision_no,
        s3_key=s3_key,
        etag=etag,
        is_current=True,
    )
    session.add(revision)
    session.flush()

    for case in cases:
        session.add(
            TaskTest(
                task_id=task.id,
                ordinal=case.ordinal,
                visibility=TestVisibility.HIDDEN,
                input=None,
                expected_output=None,
                points=case.points,
                pack_revision_id=revision.id,
                input_member=case.input,
                output_member=case.output,
            )
        )
    session.flush()
    return revision
