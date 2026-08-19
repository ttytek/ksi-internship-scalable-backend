"""Pack S3 / manifest — bez sędziego."""

from __future__ import annotations

import io
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ksi.domain.entities import Task, TaskTest, TaskTestPackRevision
from ksi.domain.enums import TaskJudgeMode, TestVisibility
from ksi.services.pack_attach import attach_main_pack
from ksi.services.storage import InMemoryStorage, ensure_cached_pack
from ksi.services.test_pack import ManifestError, build_pack, inspect_pack, parse_manifest


def _task(session: Session, slug: str = "t") -> Task:
    task = Task(
        id=uuid4(),
        slug=slug,
        title=slug,
        statement="s",
        judge_mode=TaskJudgeMode.SIMPLE,
        time_limit_ms=2000,
        memory_limit_mb=256,
        is_published=True,
    )
    session.add(task)
    session.flush()
    return task


def _sample(session: Session, task: Task, inp: str = "hello\n", out: str = "hello\n") -> TaskTest:
    row = TaskTest(
        task_id=task.id,
        ordinal=1,
        visibility=TestVisibility.PUBLIC,
        input=inp,
        expected_output=out,
        points=0,
    )
    session.add(row)
    session.flush()
    return row


def test_create_task_rejects_hidden_and_nonzero_points(client: TestClient) -> None:
    hidden = client.post(
        "/tasks",
        json={
            "slug": "hidden-not-allowed",
            "title": "X",
            "statement": "s",
            "tests": [
                {
                    "visibility": "hidden",
                    "input": "1\n",
                    "expected_output": "1\n",
                    "points": 0,
                }
            ],
        },
    )
    assert hidden.status_code == 422

    scored = client.post(
        "/tasks",
        json={
            "slug": "scored-sample",
            "title": "X",
            "statement": "s",
            "tests": [
                {
                    "visibility": "public",
                    "input": "1\n",
                    "expected_output": "1\n",
                    "points": 1,
                }
            ],
        },
    )
    assert scored.status_code == 422


def test_manifest_rejects_path_traversal_and_missing_members() -> None:
    with pytest.raises(ManifestError):
        parse_manifest(
            {"tests": [{"ordinal": 1, "input": "../x.in", "output": "1.out", "points": 1}]}
        )
    with pytest.raises(ManifestError):
        parse_manifest(
            {"tests": [{"ordinal": 1, "input": "/abs.in", "output": "1.out", "points": 1}]}
        )
    with pytest.raises(ManifestError):
        parse_manifest({"tests": []})
    with pytest.raises(ManifestError):
        parse_manifest(
            {
                "tests": [
                    {"ordinal": 1, "input": "1.in", "output": "1.out", "points": 1},
                    {"ordinal": 1, "input": "2.in", "output": "2.out", "points": 1},
                ]
            }
        )

    buf = io.BytesIO()
    with ZipFile(buf, "w") as zf:
        zf.writestr(
            "manifest.json",
            '{"tests":[{"ordinal":1,"input":"1.in","output":"1.out","points":1}]}',
        )
    with pytest.raises(ManifestError, match="missing input member"):
        inspect_pack(buf.getvalue())

    pack = build_pack([("a\n", "b\n", 2)])
    cases = inspect_pack(pack)
    assert len(cases) == 1
    assert cases[0].points == 2
    assert cases[0].input == "1.in"


def test_revision_two_keeps_old_rows(
    db_session: Session,
    fake_storage: InMemoryStorage,
) -> None:
    task = _task(db_session, "rev-task")
    _sample(db_session, task)
    rev1 = attach_main_pack(
        db_session,
        task,
        build_pack([("old\n", "old\n", 1)]),
        storage=fake_storage,
    )
    rev2 = attach_main_pack(
        db_session,
        task,
        build_pack([("new\n", "new\n", 5)]),
        storage=fake_storage,
    )
    db_session.commit()

    hidden = (
        db_session.query(TaskTest)
        .filter(
            TaskTest.task_id == task.id,
            TaskTest.visibility == TestVisibility.HIDDEN,
        )
        .all()
    )
    assert len(hidden) == 2
    assert {t.pack_revision_id for t in hidden} == {rev1.id, rev2.id}
    revs = (
        db_session.query(TaskTestPackRevision)
        .filter(TaskTestPackRevision.task_id == task.id)
        .all()
    )
    assert len(revs) == 2
    assert db_session.get(TaskTestPackRevision, rev1.id).is_current is False
    assert db_session.get(TaskTestPackRevision, rev2.id).is_current is True


def test_corrupt_cache_is_refetched(fake_storage: InMemoryStorage) -> None:
    pack = build_pack([("a\n", "b\n", 1)])
    key = "tasks/x/main/rev-1.zip"
    etag = fake_storage.put_bytes(key, pack)
    path = ensure_cached_pack(key, etag, fake_storage)
    assert fake_storage.get_count == 1
    path.write_bytes(b"not-a-zip")

    path2 = ensure_cached_pack(key, etag, fake_storage)
    assert fake_storage.get_count == 2
    with ZipFile(path2) as zf:
        assert "manifest.json" in zf.namelist()
